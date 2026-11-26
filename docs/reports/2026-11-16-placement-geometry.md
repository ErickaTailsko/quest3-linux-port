# Geometria de posicionamento após a amostra pageblock

## Conclusão

**O Image atual não cabe em nenhum trecho MOVABLE observado dentro da janela
fixa.** Não foi escolhido outro endereço nem tentada alocação no aparelho.

`tools/plan-payload-geometry.py` faz o cálculo offline com o cabeçalho Image e
o resumo da amostra autorizada. Não trata tipos amostrados como estado atual,
prova de migração, posse de páginas ou segurança DMA.

## Dimensões corretas

- Arquivo Image: 43.565.568 bytes.
- **image_size do cabeçalho: 45.219.840 bytes = 43,125 MiB.** É este espaço
  efetivo que precisa estar disponível, não apenas o tamanho do arquivo.
- text_offset=0, base alinhada a 2 MiB, flags=0xa. O bit de posicionamento
  permite base distante do início da RAM; isso não valida qualquer endereço.

Trechos contíguos formados pelos tipos MOVABLE amostrados:

| Intervalo físico, fim exclusivo | Tamanho |
|---|---:|
| [0x90000000,0x90c00000) | 12 MiB |
| [0x91000000,0x91800000) | 8 MiB |
| [0x91c00000,0x93400000) | 24 MiB |

O maior é menor que o Image isolado. Reposicionar só initramfs/DTB não basta.
Descritores de cópia podem apontar fontes dispersas, mas não tornam válido um
Image final fisicamente fragmentado em torno de pageblocks UNMOVABLE.

## Plano relativo compacto, ainda sem endereço

É possível reduzir a folga geométrica sem diminuir o kernel:

| Objeto | Offset relativo / capacidade |
|---|---|
| Image | entrada na base; slot de 44 MiB |
| Initramfs | base + 0x2c00000, capacidade 2 MiB |
| DTB | base + 0x2e00000, capacidade 2 MiB |
| Janela total | 48 MiB |

Esses offsets são apenas um cálculo. Nenhuma base foi selecionada, nenhum DT
novo foi construído para eles e o loader não foi modificado para aceitá-los.
Os limites ARM64 de initrd/DT, reservas, origem/descritores/código de transição,
posse, DMA e validação de hardware continuam obrigatórios.

## Interfaces de aquisição: não há atalho demonstrado

- alloc_contig_range está exportada, mas exige contrato vendor de cinco
  argumentos, uniformidade de tipo elegível, uma zona e lifetime adequado.
- alloc_contig_pages não está na tabela de exports stock fornecida. Não
  resolver endereço privado para reproduzir sua política por chamada indireta.
- alloc_pages_exact está exportada, mas a implementação é limitada por
  MAX_ORDER; não é uma forma genérica de obter 48/52 MiB no buddy deste kernel.
- DMA APIs dependem do dispositivo/domínio. Um dma_addr_t pode ser IOVA,
  não endereço físico; não reinterpretá-lo como destino do Image.

Também não basta procurar flags BUDDY zero/um ou somar páginas livres de uma
zona. É necessária aquisição comprovada e, separadamente, quiescência DMA.

## Continuidade recomendada

Investigar uma estratégia de destino adquirível antes de generalizar o loader:
ou região elegível validada e adquirida, ou um alvo menor com dependências
revisadas. Reduzir Image não elimina a obrigação de posse. Novas sondagens de
outras regiões ou pausas no aparelho exigem plano e autorização próprios.

Metadados: `quest3/restart-backend-design/payload-geometry.json`.
Regressões cobrem runs, image_size, arredondamento de slots, separação CMA,
evidência inválida e ausência de seleção/posse implícita. Suíte: **32 aprovações**.
