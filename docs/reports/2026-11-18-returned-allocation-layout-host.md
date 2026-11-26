# Image/initrd/DT — layout por alocações fornecidas, somente no host

**Validador host implementado; suíte completa com 61 grupos aprovados, zero
falhas/ignorados.** Esta é a próxima direção escolhida pelo usuário, mantendo
o monitor operacional bloqueado. Nenhum alocador, módulo, transporte ou comando
no Quest foi executado. Loader, candidatos e ferramentas anteriores preservados.

## Contrato novo, não integração do loader

`quest3/layout-review/returned_layout.py` recebe três registros tipados de
fixtures: Image/default-cma-image, initrd/buddy-initrd e DT/buddy-dtb. Exige
IDs distintos, mesmo attempt, proveniência fixa `host-fixture-only`, endereços
e capacidades exatos do perfil. Labels/IDs **não comprovam** retorno de API,
identidade da CMA padrão, posse de páginas ou lifetime.

O planner não procura bases, lê PFNs, chama providers, copia payloads, libera
memória ou decide unload. Os endereços de teste começam deliberadamente em
64 GiB, fora da RAM descrita pelo DT real capturado: não são uma proposta de
base para o Quest. O teste rejeita combinar essas fixtures com o DT real.

O perfil conservador usa página de 4 KiB, alinhamento/capacidade ancillary de
2 MiB e limite de PA de 48 bits, conforme a config do candidato. Isso não
valida PA/VA/mapeamento ou disponibilidade no stock em execução.

## Cabeçalho, limites e staging

- Image raw ARM64, text_offset 0 ou 512 KiB, LE e flags conhecidas de páginas
  4 KiB/não especificadas, com bit de posicionamento arbitrário; formatos,
  tamanhos e flags fora do perfil são recusados.
- Image efetiva não pode ser menor que o arquivo. O staging usa image_size
  arredondado a páginas, não apenas o tamanho do arquivo.
- A solicitação da Image cobre text_offset + staging e é arredondada a 2 MiB,
  limitada a 32 MiB neste perfil. Initrd e DT usam blocos separados de 2 MiB.
- Endereços/tamanhos têm tipos exatos, ranges sem overflow e limites de PA.
  Cada slot completo precisa caber numa extensão RAM fornecida pelo DT.
- Slots completos, incluindo prefixo/padding, não podem se sobrepor ou cruzar
  exclusões estáticas/explicitamente fornecidas. Padding não é área emprestável.
- O relatório distingue bytes de arquivo, staging, zero-fill, páginas e
  capacidade retida por alocação. Só produz dados de entry/x0/x1-x3, não dispatch.

Com o Image trim3 real:

| Medida | Bytes |
|---|---:|
| Arquivo | 31.152.640 |
| image_size/staging | 32.768.000 |
| Zero-fill até fim do staging | 1.615.360 |
| Solicitação arredondada Image | 33.554.432 |
| Initrd e DT, duas solicitações separadas | 4.194.304 |
| Total do perfil | 37.748.736 / 36 MiB |

Os 786.432 bytes restantes **dentro** do bloco Image não representam capacidade
CMA disponível fora da alocação. A identidade/capacidade livre do pool padrão
e a aquisição efetiva dos 32 MiB continuam sem validação runtime.

## Protocolo ARM64 e DT

A referência é `Documentation/arm64/booting.rst` da árvore usada no projeto:
DT alinhado a 8 bytes e de no máximo 2 MiB; Image a text_offset de base alinhada
a 2 MiB; Image e initrd inteiros numa janela física alinhada a 1 GiB de até
32 GiB. O perfil de fixtures é mais restrito para DT: bloco próprio de 2 MiB
alinhado a 2 MiB. Ainda não verifica atributos de mapeamento no hardware.

O planner calcula uma janela comum Image/initrd e rejeita a ultrapassagem de
32 GiB. O DT não é obrigado a estar nessa mesma janela nem nos antigos 512 MiB
próximos à Image: a restrição de 512 MiB era de kernels anteriores a v4.2,
não do alvo 5.10. O teste cobre DT distante e initrd antes/depois da Image.

O DT deve ter compatibilidade Quest 3 e addressing 2/2 cells revisado. Checam-se
header/seções, memory extents, memreserve e `reg` estático de reserved-memory.
Entradas RAM de tamanho zero presentes nos DTs reais são ignoradas como vazias,
nunca usadas como cobertura. `alloc-ranges` dinâmico pode abranger u64 além de
PA48: é validado como restrição de busca, **não convertido em RAM/alocação**.

Reservas dinâmicas sem posição ficam listadas como não resolvidas. O validador
não reutiliza a consulta histórica dos 13 descritores como clearance/posse atual
nem trata ausência de colisão estática como prova de segurança.

`prepare_dtb` retorna novo byte string, sem gravar arquivo. Modifica somente
`linux,initrd-start` e `linux,initrd-end` em `/chosen`, com end exclusivo usando
o tamanho real do initrd. Reconfronta todos os outros nós/propriedades, reservas
e boot CPU e revalida o tamanho após rewrite. Crescimento além do slot é recusado.
Isso é comparação semântica; o serializer pode reorganizar offsets/strings.

## Descobertas no caminho legado

O loader atual ainda depende de QKX_LO/HI, QKX_INITRD e QKX_DTB em:

1. Excluir páginas-fonte dentro da janela fixa, em `qkx_page`.
2. Validar uma janela RAM fixa e calcular entry.
3. Destinos de staging de initrd/DT.
4. Passar o DTB constante ao handoff.

Não basta trocar três constantes. A integração futura precisa usar o conjunto
de faixas efetivamente adquiridas para fontes, descritores e scratch, manter
handles/lifetime e separar endereços/recursos de cada payload. Essa parte não foi
implementada ou habilitada. O bloqueio CFI dos caminhos privados permanece.

## Testes, procedência e limites

`test-returned-layout.py` cobre bounds/types/overflow, flags/offsets, slots
adjacentes/sobrepostos, aliases de IDs/contextos, providers desviados, padding,
janela initrd, DT distante, exclusões estáticas e extras, RAM vazia/ambígua,
constraints dinâmicos u64 e crescimento/rewrite somente de chosen.

O teste confere medidas/hashes reais do trim3 e initrd, mas planeja seus endereços
apenas com DT/RAM sintéticos. Também faz parsing read-only do DT stock capturado
e do DT USB candidato, que **não são o mesmo artefato**. O assessment anterior
referencia o live.dtb capturado de 698.964 bytes, não o DT USB candidato de
698.940 bytes; não houve substituição ou regravação de nenhum deles.

Fontes, testes, log, exemplo de plano/DT inteiramente sintéticos, medidas e hashes
estão em `private-diagnostics/returned-layout-host-01/`. Não se produziu DT de
boot para um endereço real novo. Loader/header fixos, controlador, módulo de
identidade, Image e artefatos Android anteriores foram reconferidos por hash.

Todas as flags de execução, allocator_called/authorized, ownership, PFNs,
layout de boot atual, atributos DT, completude de reservas, DMA, fontes/scratch,
integração com loader, cleanup e boot_ready permanecem falsas. Geometria não é
autorização para carga de módulo, aquisição ou handoff.

## Próximo gate

Revisar representação e validador C das faixas retornadas e sua integração futura
com staging/descritores/exclusão de páginas, ainda desarmados. Aquisição real
continua dependendo de identidade/lifetime da CMA padrão, política de buddy,
impacto, rollback e nova autorização específica. CPUs, DMA/SMMU, watchdog, QMP,
handoff CFI e logs recuperáveis continuam gates independentes antes do primeiro
boot alternativo. O monitor operacional segue bloqueado por sua âncora externa.
