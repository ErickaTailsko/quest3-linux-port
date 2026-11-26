# Layout separado — núcleo C aritmético e consulta de destinos, somente host

**Núcleo C implementado e testado no host: 62 grupos aprovados, zero falhas e
zero ignorados na suíte completa.** Não houve integração com o loader, chamada
de alocador, build kernel/Android, transferência ou operação no Quest.

## Escopo deliberadamente menor que o validador Python

`quest3/layout-review/returned-layout-core.h` contém funções inline de geometria
e interseção. O loader ativo **não inclui esse header**. O teste nativo usa o
ramo `Q3RL_HOST_TEST`, com tipos u64 e errno do host. O ramo de includes Linux
existe para revisão futura, mas não foi compilado/integrado ao kernel nesta etapa.

O caller fornece campos numéricos já extraídos do Image, comprimentos dos outros
payloads e três slots com papel/família de provider/start/capacidade. A ordem dos
slots pode variar; papéis repetidos/desconhecidos e providers incompatíveis são
recusados. Enums de provider são **labels**, não prova de identidade runtime.

| Checagem | Núcleo C desta etapa |
|---|---|
| Bounds u64/PA48, align, offset/size/flags numéricos | Sim |
| Slots separados, capacidades e não sobreposição completa | Sim |
| Staging page-rounded, zero-fill e janela Image/initrd | Sim |
| Magic/header completo, conteúdo do initrd e hashes | Não |
| DT board/RAM/reservas/chosen e rewrite | Não; continuam no verificador Python |
| IDs/attempt, handles reais, posse e lifetime | Não |
| DMA, CPU, caches/MMU, watchdog, CFI handoff e boot | Não |

No sucesso numérico, o resultado declara `geometry_only=1`, `ownership_acquired=0`
e `boot_ready=0`. Em erro, nenhuma saída nova é publicada. Isso não é uma
estrutura wire nem um objeto de admissão.
Os testes incluem propositalmente metadados de um DT cuja RAM é insuficiente
e registros com attempt errado: a geometria numérica pode passar, enquanto o
validador Python recusa os checks adicionais. Não se deve substituir o conjunto
de guards pelo retorno zero dessa função.

## Aritmética e contrato de erro

O perfil preserva páginas de 4 KiB, alinhamento/slots ancillary de 2 MiB, PA48,
Image de até 32 MiB arredondados, text_offset 0/512 KiB e flags LE/4K/placement
conhecidas. Image e initrd precisam compartilhar janela física alinhada a
1 GiB de até 32 GiB. DT não ganha a antiga restrição de proximidade de 512 MiB.

Todos os bounds precedem adição/arredondamento. O tamanho efetivo do Image, não
apenas o arquivo, determina staging e zero-fill. Os ranges são semiabertos;
fim exclusivo exatamente em 2^48 é permitido, mas não é um endereço acessado.
Ranges nulos, overflow, flags/roles fora do perfil e capacidades divergentes
são recusados. O resultado é construído localmente e publicado só no sucesso:
**saídas do caller permanecem intocadas em todos os erros**.

## União dos três destinos para futuras páginas-fonte/scratch

`q3rl_destination_overlap_mask` revalida a geometria e recebe um range numérico.
Retorna bits de interseção com os slots **inteiros**:

- bit 0 / valor 1: Image;
- bit 1 / valor 2: initrd;
- bit 2 / valor 4: DT.

Prefixo text_offset, padding/BSS/tail e restante retido pelo pedido arredondado
também pertencem ao destino. A consulta não usa o antigo intervalo fixo nem
transforma gaps entre slots em destinos. Pode representar páginas-fonte,
descritores, código de relocação, page tables ou scratch sem acessar seus bytes.

**Máscara zero significa somente ausência de interseção com esses três slots.**
Não comprova RAM válida, PFNs presentes, propriedade, atributos ou disponibilidade.
Não valida aliases entre os próprios recursos de trabalho. Um retorno negativo
também não é máscara zero: o caller deve bloquear o caminho ao receber erro,
sem interpretar um valor antigo deixado na saída.

O `qkx_page` do loader continua usando sua janela fixa e não foi modificado.
Seu adaptador futuro terá de usar faixas realmente adquiridas, manter handles
vivos e tratar os erros. Esta etapa não troca constantes nem habilita o handoff.

## Testes executados

`test-returned-layout-core.py` compila somente uma biblioteca nativa de fixture
com warnings como erro, UBSan sem recover, stack protector, FORTIFY e RELRO/NOW.
Executa funções de aritmética no host via ctypes, nunca código ARM64/Android.
Isso não valida ABI kernel, enforcement CFI ou runtime SCS do alvo; as proteções
e artefatos anteriores permanecem inalterados.

São comparados os campos comuns com `returned_layout.py`, incluindo medidas
reais do trim3 sob RAM/endereços fictícios. O teste tem **2.000 casos aleatórios
reproduzíveis**, seed 20261118, além de casos explícitos de:

- offsets, flags, page rounding, slots adjacentes/sobrepostos e DT distante;
- endpoints PA48/UINT64, slots/papéis inválidos, NULL e saída preservada;
- janela initrd de 32 GiB e sua ultrapassagem;
- máscara de fonte/descritor/código/page-table/scratch em prefixo e padding;
- ranges que cruzam vários destinos, gaps e ranges físicos inválidos;
- diferença intencional entre geometria numérica e checks de DT/contexto.

Fontes/harness, binário nativo de teste, log/flags/versão do compilador, resumo
diferencial, vetor público de metadados e suíte/hashes são preservados em
`private-diagnostics/returned-layout-c-core-host-01/`. O binário é uma fixture do
host, não módulo kernel ou artefato de deployment. Loader/header fixos, Python
anterior, controlador, Image, módulo de identidade e ELFs Android anteriores
foram reconferidos por hash.

## Próximo gate

Revisar representação/lifetime dos recursos reais e plano de staging/descritores,
incluindo aliases entre fontes e scratch e prova de que os handles cobrem todas
as páginas. Só então projetar adaptador C desarmado e validação no build do alvo.
Aquisição continua sem autorização e sem runtime validado. CFI-compatible handoff,
CPU/DMA/SMMU, watchdog/QMP e logs recuperáveis permanecem gates independentes.
Nenhum resultado desta etapa permite boot, cleanup ou operação no Quest.
