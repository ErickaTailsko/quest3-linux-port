# Staging/descritores — recursos e snapshots de host, sem handoff

**Modelo host implementado; 63 grupos aprovados, zero falhas/ignorados.** Foram
modeladas páginas-fonte, descritores e recursos auxiliares com exclusão mútua e
exclusão dos destinos. Nenhum alocador, leitura/escrita física, build kernel/
Android, transferência ou comando no Quest foi executado.

## Representação e fronteira de confiança

`quest3/layout-review/relocation_plan.py` usa registros imutáveis de fixtures:

- Allocation: três destinos do perfil anterior, com role/provider/ID/attempt.
- Page: uma página de trabalho de 4 KiB, kind/ID/attempt/índice/endereço fictício.
- Copy: source/destination por página, role/índice, hash do snapshot e contagem
  de bytes de arquivo/zero-fill.
- Descriptor: bytes de uma página de descritores produzidos **no host**.

IDs são distintos entre destinos, páginas de trabalho e attempt. Conteúdo de
source é um snapshot bytes imutável de fixture, não readback de uma página no
Quest. Código, PGD, PUD e scratch são registros geométricos sem conteúdo: não se
construiu código de relocação, tabela de páginas ou mapeamento arquitetural.

O modelo exige um recurso de código, um PGD e um PUD, como o caminho normal
legado; permite até 16 páginas scratch explícitas. Não é inventário completo
dos recursos vivos do kernel antigo ou de seus caminhos de rehearsal.

## Validação antes de produzir descritores

O builder reexecuta o plano de destinos e exige DT com chosen/initrd já
preparado; não reescreve DT silenciosamente. Cada página de trabalho precisa
ser tipada, alinhada, bounded em PA48, estar numa extensão RAM do DT fornecido
e não colidir com reservas estáticas. Reservas dinâmicas continuam sem prova
de localização/lifetime atuais.

Todos os recursos de trabalho são ordenados por endereço e confrontados entre
si, incluindo sources, descritores, código, PGD/PUD e scratch. Também são
confrontados com os três slots de destino completos, inclusive prefixo
text_offset e padding. Alias de ID, endereço, role/índice ou recursos faltantes/
extras são recusados; não há fallback de provider nem liberação automática.

Sources devem cobrir exatamente todas as páginas de staging de Image/initrd/DT.
O conteúdo é comparado aos bytes do payload e ao zero-fill até o fim de cada
página, incluindo o image_size efetivo e BSS/tail. Fontes podem ser fisicamente
esparsas na fixture; os destinos de cada payload continuam sendo contíguos.

## Formato dos descritores, não execução da assembly

Foi revisado o formato usado atualmente por `loader.c` e `transition.S`:
next u64, count u64 e até 255 pares source/destination u64 em página de 4 KiB.
O modelo serializa esses campos em little-endian, zera a parte não usada,
encadeia exatamente as páginas fornecidas e termina com next=0.

O verificador percorre somente um dicionário de **bytes de host fornecidos**,
nunca um ponteiro físico. Confere identidade das páginas, count/links/ordem,
pares exatos, tail zero, término e ausência de páginas faltantes/não alcançadas.
Ciclos, links estrangeiros, count fora de 1..255 e pares adulterados são
rejeitados com limites de iteração/dados. A ordem do array de input pode variar;
a ordem da cadeia é a definida pelo plano.

Isso espelha apenas o formato do projeto atual. Não é transplante de endereço
ou patch do Quest Pro e não valida a sequência EL1, cache/MMU, x18/SCS, CFI,
CPU shutdown ou quiescência de dispositivos da assembly. Os fontes ativos
continuam intactos, com os bloqueios anteriores preservados.

## Retenção de registros não comprova lifetime

O plano registra hashes dos payloads e um compromisso contextual dos registros
de destinos/páginas/snapshots. Uma comparação posterior dos registros fornecidos
rejeita perda, substituição, mudança de contexto/endereço ou alteração de bytes.

Porém, repetir snapshots e IDs idênticos também coincide, mesmo sem qualquer
prova de que a página física ainda exista ou continue alocada. O teste demonstra
essa limitação. **Não há handles kernel, pinagem real ou autorização de unload**
por trás dos objetos Python, nem API de release/execução/retomada.

Mesmo sucesso mantém falsos ownership, actual_handles_live_verified, PFNs,
layout atual, lifetime, readback físico, payload/descritores escritos no alvo,
tabelas construídas, código/CFI handoff, DMA, impacto runtime, integração com
loader, cleanup, retomada e boot_ready.

## Orçamento novo: destinos não são o custo total do staging

O cenário maior usa Image trim3 e initrd reais, mas DT/RAM/endereço/recursos
**inteiramente de fixtures**. O DT sintético tem padding que produz 171 páginas,
próximo do tamanho dos DTs existentes; não é o DT stock/candidato regravado.

| Recursos da fixture | Quantidade | Bytes |
|---|---:|---:|
| Destinos Image/initrd/DT | 3 blocos | 37.748.736 / 36 MiB |
| Sources: Image 8.000 + initrd 146 + DT 171 | 8.317 páginas | 34.066.432 |
| Descritores | 33 páginas | 135.168 |
| Código + PGD + PUD (só metadados) | 3 páginas | 12.288 |
| Trabalho total | 8.353 páginas | 34.213.888 / 32,62890625 MiB |
| Destinos + trabalho contabilizado | — | **71.962.624 / 68,62890625 MiB** |

Os 36 MiB anteriores eram somente solicitações de **destino**, não orçamento
completo do loader com cópia por relocação. Essa conta não inclui page cache,
páginas rejeitadas/retidas, bookkeeping, stacks ou outros recursos do kernel.
Não prova capacidade disponível, custo real ou que todos esses recursos possam
ser adquiridos juntos. O limite de 32.768 registros de trabalho é uma barreira
do modelo, não validação de pressão/impacto do alocador stock.

## Testes e preservação

`test-relocation-plan.py` cobre snapshots/tails/BSS, sources esparsas, IDs/attempt,
alias entre todos os kinds, destino/padding, RAM/reserva estática, recursos
faltantes/extras, índices, chosen não preparado e corrupção de descritores.
Exercita fronteiras de 254/255/256/510/511 cópias e testa perda/substituição de
registros retidos, mantendo explícita a ausência de liveness real.

Fontes, log, ledger e mapa de cópias sintéticos, páginas binárias de descritores
de fixtures, DT sintético e suíte/hashes são preservados em
`private-diagnostics/relocation-staging-plan-host-01/`. Esses binários não são
inputs de boot aceitos pelo loader nem foram transferidos. Loader, assembly,
header fixo, núcleo C/Python anterior, controlador, Image, módulo de identidade
e ELFs Android anteriores foram reconferidos por hash.

## Próximo gate

Comparar offline a estratégia de cópia por relocação com a hipótese de staging
direto em destinos **realmente adquiridos**, considerando orçamento, lifetime,
cache e rollback. Não habilitar escrita direta ou aquisição por causa dessa
comparação. Antes de qualquer adaptador C/loader, são necessários handles reais,
guardas de lifetime, validação no alvo e revisão dos gates de handoff/logs.
Qualquer operação no Quest continua exigindo nova autorização específica.
