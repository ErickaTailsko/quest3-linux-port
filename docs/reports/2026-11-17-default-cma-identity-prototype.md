# Identidade CMA padrão — protótipo e controlador testados no host

> Atualização posterior: [build stock ARM64 e verificações concluídos](2026-11-17-default-cma-identity-build.md).
> As referências abaixo a build ainda pendente registram a etapa do protótipo.
> O controlador permanece desarmado e nenhuma operação no Quest foi realizada.
> **Correção posterior de transporte:** a reconciliação automática após resposta
> perdida descrita neste registro foi substituída por bloqueio até comprovar
> término remoto. Veja a [revisão de recuperação](2026-11-17-cma-transport-recovery-review.md).

**Consulta implementada no fonte e testada com mocks. Nenhuma operação no
Quest, nenhum binário ARM64 novo construído e nenhuma identidade runtime
confirmada.** O controlador não tem transporte real e mantém o hash de módulo
aprovado desabilitado. O consentimento anterior não foi reutilizado.

## Implementação

Novo diretório: `quest3/cma-identity-query/`.

- `q3_cma_identity.c` e Makefile: consulta tipada do único nó linux,cma,
  opt-in e token da tentativa, guardas de plataforma/config/proteções e asserts
  do layout público de reserved_mem. Nenhum acesso a campos privados de CMA.
- Antes de cma_get_name, exige propriedades DT esperadas, descritor de 32 MiB,
  base não nula/alinhada em 4 MiB, fim dentro dos 4 GiB baixos e igualdade não
  nula do ponteiro padrão com priv. Não fixa o endereço observado anteriormente.
- Reobserva os ponteiros após o nome; isso detecta inconsistências, mas não
  fornece referência de lifetime, lock de hotplug ou prova contra ABA.
- Relatório estático, bounded, root-only: versão, token, etapa, erro e flags
  de identidade. Falha de consulta pode ser registrada num relatório rejeitado;
  não é aprovação parcial. Leituras sysfs não repetem a consulta.
- Erros de inicialização de metadados devolvem kobject; todos os caminhos após
  localizar o nó devolvem sua referência OF. Exit remove sysfs e kobject.

Etapas do relatório: 1 nó; 2 propriedades; 3 descritor; 4 igualdade; 5 nome;
6 reobservação; 7 snapshot consistente. Apenas etapa 7 com erro zero admite
identity_observed=1. O parser exige consistência das flags intermediárias.
allocator_called, availability_proven, ownership_acquired,
allocation_experiment_ready e boot_ready permanecem zero inclusive no sucesso.

## Controlador sem backend real

`controller.py` aceita somente transporte injetado; nenhum adaptador ADB/shell
é fornecido. `EXPECTED_MODULE = None` impede entrar na coleta e o entry point
de script encerra sem operar. Somente testes alteram o valor em memória para
um hash de bytes sintéticos; nenhum binário revisado foi declarado.

A transação modela raiz existente, release, hashes exatos de config/DT, boot,
CPU mask válida e ausência de módulo, sysfs e caminho temporário. Hashes de
config/DT são os do stock arquivado, não evidência de uma nova sessão.
Usa transferência em chunks de 4 KiB e valida tamanho/hash antes da inserção.
Criação do temporário exige confirmação explícita e não usa clobber.

O journal privado é escrito por replace com fsync do arquivo e diretório;
o contador da única tentativa é persistido **antes** do comando insmod. Diretório
de evidência existente nunca é retomado/sobrescrito. Isso evita repetição
automática nesta transação, mas não é um serviço global de consentimento:
outro diretório não autoriza nova carga.

O token exclusivo também aparece no relatório do módulo. Mesmo após resposta
perdida de insmod, cleanup só considera unload se o relatório atual tiver o
token correto e esquema válido no mesmo boot observado. Um relatório de
identidade rejeitada pode permitir cleanup da própria tentativa; não permite
alocação. Relatório inválido/de outra tentativa, mudança de boot, módulo
inesperado ou propriedade incerta do temporário deixam o estado pendente para
revisão. Não há unload/delete cego nem retry de insmod/rmmod após resposta incerta.

Se a criação do arquivo perdeu sua confirmação, não há prova suficiente para
apagá-lo automaticamente; se um chunk posterior falha após criação confirmada,
o controlador pode limpar somente seu arquivo conhecido. Respostas perdidas de
consulta podem ser reconciliadas lendo o relatório **já armazenado**, sem
nova consulta ao CMA. Falha anterior continua falha, mesmo com cleanup confirmado.

Os checks sequenciais não são uma trava atômica contra reboot concorrente ou
outro gerenciador de módulos. Execução exclusiva, revisão do transporte e
reconciliação manual de estados incertos continuam requisitos de uma versão live.

## Testes e limites

`test-query.py` extrai e compila os corpos reais de query/init/exit/report com
CC do host, -Wall/-Wextra/-Werror e mocks. Cobre propriedades ausentes/incorretas,
limites/overflow, igualdade antes do accessor, nome inesperado, reobservação,
gates de init, falhas kobject/sysfs, limpeza OF e leitura sem repetir consulta.
Uma allowlist de chamadas da query e verificações de fonte rejeitam aquisição
de payload, callbacks e sondagens fora do escopo.

`test-controller.py` valida o parser e simula preflight rejeitado, estado
preexistente, corrupção/tamanho incorreto na transferência, respostas perdidas,
boot mudando antes da inserção/durante cleanup, módulo concorrente, token alheio,
relatório inválido/rejeitado, falhas de unload/delete e mudança de CPUs.
Confere intenção já persistida no momento de insmod e no máximo uma tentativa.

Suíte completa: **44 aprovações, zero falhas e zero testes ignorados**.
Resultado privado: `private-diagnostics/host-tests.json`.

Esses testes não compilam o módulo completo contra headers ARM64; asserts de
layout/guardas no fonte não equivalem a ABI ou flags de compilação verificadas.
Ainda faltam build stock separado, revisão de imports/CRCs e CFI/SCS/Full LTO,
revisão do lifetime aplicável e implementação/revisão de eventual transporte.
Uma carga exigirá consentimento próprio; nenhum desses passos autoriza aquisição
de páginas. O trim3 segue com Image de 31,25 MiB e pedido arredondado de todos
os 32 MiB nominais, sem disponibilidade comprovada ou layout separado no loader.

Próximo marco seguro: preparar **somente no host** o build stock da consulta e
verificar o artefato/imports/proteções, preservando a trava de implantação.
