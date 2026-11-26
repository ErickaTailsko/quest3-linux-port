# Imports, política explícita e vínculo de conteúdo — módulo host

**69 grupos host aprovados, zero falhas/ignorados.**
`quest3/layout-review/cache_leaf_import_review.py` torna reutilizável parte da
[auditoria anterior](2026-11-19-cache-leaf-parser-caller-evidence-review.md).
É uma API pura de bytes e registros: não abre arquivos, executa comandos, carrega
módulos, constrói artefatos ou opera no Quest.

Nenhum helper, wrapper operacional, adaptador ou alteração do loader foi criado.
O progresso global permanece estimativa subjetiva de ~40%.

## Interface e política obrigatoriamente explícita

`review` recebe ELF e symvers em bytes imutáveis, uma política opcional de
`ImportRule` imutáveis e, opcionalmente, hashes esperados. Não infere política
do próprio ELF e não possui catálogo operacional default.

Cada regra especifica **nome, CRC uint32, provedor, tipo de export e namespace**.
Uma política fornecida precisa cobrir exatamente o conjunto de versões,
incluindo `module_layout`: faltas, extras e duplicatas são recusadas. Todos os
campos devem coincidir com a tabela stock fornecida, não apenas o nome/CRC.
Política ausente fica PENDING, mesmo que os CRCs sejam compatíveis.

Uma política é input declarado pelo caller, **não credencial de autorização**.
O catálogo histórico usado nos testes vem da auditoria arquivada anterior,
independentemente do ELF inspecionado, e serve somente como referência local.
Não foi transformado em allowlist para um futuro módulo/helper.

## Checagens de interface

O parser ELF bounded existente é reutilizado para estrutura/seções/símbolos;
este novo módulo não executa a análise de instruções/PAC/call graph do leaf.
Exige, quando há metadados de módulo:

- Par único `__versions`/`.modinfo`, ambos PROGBITS. Ausência de ambos é PENDING;
  par incompleto, duplicado ou malformado é REJECT neste perfil MODVERSIONS.
- Registros ARM64 de 64 bytes: CRC nos primeiros 8 bytes limitado a uint32,
  nome ASCII terminado e padding zero, sem duplicatas.
- Conjunto de versões exatamente igual aos símbolos indefinidos mais
  `module_layout`, sem indefinidos duplicados.
- Presença do export e igualdade de CRC na tabela fornecida.
- Namespace exigido pelo export declarado em `import_ns`, sem duplicação.
- Compatibilidade do **token de licença registrado** com exports GPL no perfil
  restrito suportado; isso não é verificação jurídica da licença do conteúdo.
- Dependências declaradas exatamente iguais aos nomes modulares derivados dos
  providers. Não tratar provider modular como vmlinux. Provedores de caminhos
  distintos com o mesmo basename são ambíguos e recusados.

O perfil usa nomes de dependência exatos, sem adivinhar equivalência por aliases
ou normalização de hífen/underscore. Também não verifica completamente vermagic,
inicialização de módulo, ABI C ou resolução/lifetime reais. Metadados coerentes
não bastam para concluir que um ELF é um módulo operacional válido.

Limites adicionais: symvers até 8 MiB/65.536 linhas, linha até 512 bytes;
política/versões até 1.024 entradas; modinfo até 64 KiB/1.024 registros com
comprimento individual limitado. ASCII, tipos e campos são validados sem
interpretação de caminhos, namespaces ou texto como comandos.

## Conteúdo vinculado não equivale a proveniência

Hashes esperados, se fornecidos, devem conter exatamente `elf`, `symvers` e
`policy`. Divergência ou conjunto parcial/extra é REJECT. Sem hashes, o vínculo
de conteúdo fica PENDING. A política tem serialização canônica ordenada por nome
e SHA-256 com domínio `Q3-LEAF-IMPORT-POLICY-V1`.

Isso detecta substituição **em relação aos hashes fornecidos**, não estabelece
quem os aprovou nem que houve compilação com aquelas fontes/configs. O teste de
substituição coerente troca ELF, tabela, política e todos os hashes juntos:
as checagens locais podem passar, mas o resultado global continua PENDING e
`source_to_binary_build_relation_proven` continua falso. Âncora externa,
rollback e autorização não são resolvidos por esse mecanismo.

## Resultados independentes

O relatório separa `elf_metadata`, `stock_table`, `interface_match`,
`explicit_policy` e `content_binding`, cada um com PASS/PENDING/REJECT.
`metadata_consistent` só é true quando todos esses checks locais têm PASS.
**O resultado global nunca é PASS**, mesmo nesse caso.

`leaf_contract_evaluated` permanece falso: esse módulo não substitui o verificador
anterior. No controle histórico, por exemplo, os metadados ficam consistentes e
o resultado desta API é PENDING, mas a análise separada do leaf continua
**REJECT em L08**. Nenhum resultado daqui revoga essa rejeição.

Build, ABI C completa, CFI dos callers, cache, lifetime, autorização,
helper_approved, execução, cleanup, retomada e boot_ready não são promovidos a
verdadeiros. Não há API de release/retry/entrada nem backend de dispositivo.

## Testes

`test-cache-leaf-import-review.py` cobre:

- Política exata, ordem canônica e ausência de política/hashes sem inferência.
- CRC, provider, tipo de export e namespace alterados; exports e regras
  duplicados, ausentes ou extras; tipos/limites inválidos.
- Namespace não declarado/duplicado, token de licença incompatível, dependência
  faltante/extra e providers ambíguos por basename.
- Versões e indefinidos inconsistentes, module_layout ausente, registros/padding/
  CRC inválidos, metadados ausentes/incompletos/duplicados e limites de tamanho.
- Hash parcial/extra/divergente, alteração de conteúdo com pins antigos e
  substituição conjunta coerente que **não** comprova build/autorização.
- ELF histórico: 72 versões, 71 indefinidos e dependência qcom-scm, confrontados
  com catálogo arquivado e symvers; a rejeição PAC do verificador anterior é
  reconferida independentemente.

As fixtures contêm registros `.modinfo`/`__versions` inventados sobre ELF
**não ligado**, sem estrutura de módulo operacional, build, carga ou execução
de instruções inspecionadas. Não são um helper candidato.

## Próximo gate

Checagens reutilizáveis de metadados e conteúdo concluídas. Ainda falta um pacote
completo de evidências de fonte/config/dependências transitivas/comandos/toolchain
e caller ABI para um futuro candidato. Próximo passo seguro: especificar esse
pacote e o plano de build offline isolado, antes de implementar/construir helper;
sem incorporar código ao loader ou habilitar operação no aparelho.

Evidência: `private-diagnostics/cache-leaf-import-review-host-01/`, com código,
testes, fixtures, política histórica marcada como referência, relatórios e hashes.
