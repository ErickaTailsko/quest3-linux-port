# Posse de RAM: contrato e observação somente leitura

## Coleta no Quest

Foram lidos identidade/root, release, tamanho de página, boot IDs,
`/proc/zoneinfo`, `/proc/pagetypeinfo`, `/proc/iomem` e apenas os registros
kpageflags/kpagecount correspondentes à janela `[0x90000000,0x93400000)`.
Não foram lidos conteúdos de páginas físicas, carregados módulos, migradas ou
reservadas páginas, alterados serviços ou solicitados resets.

Kernel e páginas conferem com o ambiente conhecido; boot ID antes/depois igual.
Cada arquivo kpage contém 106.496 bytes: 13.312 registros de 8 bytes para
13.312 páginas de 4 KiB. As leituras são separadas e não atômicas.

## Resultado observado

| Metadado | Entradas/páginas marcadas |
|---|---:|
| SLAB | 73 |
| PGTABLE | 11 |
| LRU | 7.113 |
| ANON | 6.577 |
| BUDDY | 1.072 |
| Contador de mapeamentos não zero | 6.762 |
| Flags inteiramente zero | 1.641 |

Flags não são categorias disjuntas; não somar as linhas como partições da RAM.
BUDDY marca cabeças de blocos livres, não todas as páginas livres. Flags zero
e mapcount zero não significam página livre, posse do loader ou ausência de DMA.
Contagens de páginas compostas também exigem cuidado. Não correlacionar os dois
arquivos como um snapshot simultâneo de cada PFN.

Os dados contradizem a hipótese de que toda a janela esteja simplesmente livre
para sobrescrita. Não comprovam que uma futura alocação contígua falharia ou
teria sucesso: memória e mapeamentos continuam mudando.

Segundo zoneinfo, a janela cabe no span observado da zona DMA. Pagetypeinfo
indica pageblock_order=10, 1.024 páginas/bloco (4 MiB): a janela é alinhada a
esses blocos e ocupa 13 blocos. Pagetypeinfo só fornece totais por zona/tipo;
não identifica o migratetype dos 13 blocos físicos selecionados. Span de zona
também não prova, sozinho, validade e elegibilidade de cada PFN.

## ABI vendor: detalhe obrigatório

Na revisão pública fixada, include/linux/gfp.h declara:

```c
int alloc_contig_range(unsigned long start, unsigned long end,
                       unsigned migratetype, gfp_t gfp_mask,
                       struct acr_info *info);
```

**São cinco argumentos**, não a assinatura genérica de quatro. A implementação
usa info para erros/contadores, portanto não passar NULL nem inventar uma struct
de outra versão. Usar header correspondente e inicialização explícita dos
campos; end é PFN exclusivo, não endereço físico ou número de páginas.

O contrato documentado exige uma única zona e pageblocks com mesmo migratetype
MOVABLE ou CMA. A função isola blocos, migra/reclama páginas e pode retornar
erro; não é uma sondagem passiva. Sucesso concede as páginas no intervalo ao
chamador, que deve liberá-las com free_contig_range. Não usar __free_pages ou
liberar intervalos cuja aquisição não tenha sido confirmada.

A tabela stock fornecida exporta alloc_contig_range, free_contig_range,
get_pfnblock_flags_mask e pfn_valid. Isso permite investigar uma futura sondagem
tipada, mas não prova equivalência completa da ABI interna ou segurança de uso.

## Próximo contrato de implementação

1. Sondagem estritamente RO de PFNs, zona e migratetype de cada pageblock,
   com os headers/ABI stock corretos e sem endereços arbitrários fornecidos.
2. Não adivinhar MIGRATE_MOVABLE nem selecionar CMA apenas por parecer livre.
3. Se uma aquisição experimental vier a ser autorizada, separar estado NEW,
   ACQUIRING, OWNED e RELEASED; não habilitar salto por mero retorno zero.
4. Definir liberação única, caminhos de erro, posse do módulo e exclusão de
   fontes/descritores/código/pilhas. Proibir aquisição após commit/IRQ-off.
5. Validar separadamente DMA/SMMU: posse pelo alocador não bloqueia um dispositivo
   com mapeamento anterior, nem substitui o protocolo de shutdown.

Nenhuma chamada de aquisição foi feita. A eventual sondagem por novo módulo
exige build stock adequado e autorização própria antes de carga; módulos do
candidato QMP não devem ser usados no Android stock.

## Evidências e reprodução

Brutos privados: `private-diagnostics/memory-feasibility-01/`, ignorados pelo Git.
Resumo revisado: `quest3/restart-backend-design/memory-window-analysis.json`.
Analisador offline: `tools/analyze-memory-window.py`. Testes sintéticos integrados
à suíte, agora com **28 aprovações, zero falhas/ignorados**. Nenhuma análise
declara posse, viabilidade de alocação, DMA seguro ou readiness para boot.
