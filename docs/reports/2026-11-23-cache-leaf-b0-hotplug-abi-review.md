# B0 — limites de hotplug, geometria e retenção

Revisão textual offline; sem fontes candidatas, build ou operação no Quest.
Complementa a [primeira revisão B0](2026-11-23-cache-leaf-b0-source-review.md).
**B0 continua PENDING. Nenhuma ABI ou política executável foi alterada.**

## CTR sanitizado não é um snapshot com lifetime comprovado

Na árvore local:

1. `arch/arm64/kernel/smp.c:233–247` verifica capabilities da CPU secundária
   e depois chama `cpuinfo_store_cpu()`, antes de marcá-la online.
2. `cpuinfo.c:414–418` chama `update_cpu_features()`.
3. `cpufeature.c:1144–1145` atualiza o registro de CTR; o caminho
   `check_update_ftr_reg()` (1007–1019) chama `update_cpu_ftr_reg()`
   **antes** de testar diferenças no strict mask.
4. `update_cpu_ftr_reg()` (990–1003) calcula o valor seguro e escreve `sys_val`.
   O leitor público (1234–1242) retorna esse campo, sem adquirir um pin ou lock.
5. `check_local_cpu_capabilities()` (2892–2909) distingue capabilities
   finalizadas das não finalizadas. Isso, isoladamente, não prova que o caminho
   de atualização acima deixa de existir.

A config preparada habilita `CONFIG_HOTPLUG_CPU=y`. Não inferir imutabilidade
da tabela apenas de o sistema ter terminado o boot. Também não concluir que
qualquer CPU incompatível será aceita: há verificação anterior, e sua cobertura
precisa ser analisada separadamente. Esta revisão não demonstra uma corrida
observada nem falha concreta no Quest.

Consequência: um valor obtido previamente não é autorização perpétua para um
passo de loop. Um hipotético caller precisa demonstrar domínio de CPUs e
estabilidade da geometria durante todo o uso. Ler duas vezes e comparar não
prova ausência de mudança no intervalo. Fixar migração não exclui por si só
hotplug de outras CPUs.

Não propor manter lock de hotplug através do shutdown: a revisão anterior
identificou possível ciclo de locks nessa composição. Uma seção pré-shutdown
com geometria estável não aprova automaticamente a mesma função pós-shutdown.
Não adicionar locks nem comandos de CPU nesta etapa documental.

## Incompatibilidade de interface permanece explícita

O perfil `q3-cache-leaf-acceptance-contract-host-v1` especifica apenas:
retorno void, argumento VA e comprimento em bytes. Não existe argumento de
geometria. L07 restringe os registradores de trabalho e proíbe calls no leaf.

Logo, descobrir uma consulta pública no caller **não fecha** a forma de fazer
essa informação chegar ao leaf:

| Hipótese | Estado |
|---|---|
| Terceiro argumento de linha | Exige novo perfil/ABI, declaração, critérios e revisão do verificador |
| Global mutável/cacheado | Acrescenta dependência e lifetime/sincronização; não é substituto silencioso de argumento |
| Chamar leitor público dentro do leaf | Viola a ausência de calls do perfil atual |
| CTR raw local | Não resolve automaticamente heterogeneidade/contexto |
| Constante ou CWG máximo | Não há prova para usar como passo |

Não selecionar nenhuma dessas opções por conveniência. Próxima decisão
documental: especificar uma proposta versionada de geometria explícita, ou
demonstrar solução que cumpra integralmente v1. Isso não autoriza implementar
nenhuma delas. Mesmo nova ABI não resolveria erratas, mappings ou PoC.

## Retenção: suporte fonte não equivale a prova do artefato

A config preparada habilita `CONFIG_FRAME_POINTER=y`. No Makefile raiz
(866–867), esse ramo acrescenta `-fno-omit-frame-pointer` e
`-fno-optimize-sibling-calls`. Isso favorece a exigência de chamada com retorno,
mas não prova comandos efetivos nem presença de BL após Full LTO.

`__used`/`noinline` continuam propostas não testadas. Não publicar o endereço
do helper nem criar callback/init operacional para impedir eliminação.
O futuro gate B4 exige presença real de caller e destino, tipo compatível,
call direto, PAC/BTI e preservação SCS/x18; se não houver evidência, PENDING
ou REJECT conforme o caso. Sem flags de bypass.

## Resultado e próximo gate

Avanço documental: identificados caminho de atualização do CTR, limite do
argumento de capabilities finalizadas e incompatibilidade explícita da
geometria externa com a ABI v1. Não há novo teste funcional de CPU/cache,
helper aprovado, posse de RAM ou confirmação de boot.

Próximo passo: proposta documental versionada da ABI/geometria e seus limites
de contexto; manter candidato/build/loader/dispositivo ausentes. Progresso
global permanece ~40% subjetivo.
