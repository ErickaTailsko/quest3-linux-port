# Preparação do novo candidato QMP

**Atualização final:** Image e módulos terminaram com sucesso; artefatos e
layout passaram nas verificações. Veja o [resultado final](2026-11-16-qmp-build-result.md).
Os estados pendentes abaixo são históricos, preservados para rastreabilidade.

## Progresso: objetos compilados e Full LTO iniciado

O build chegou a `LTO vmlinux.o`. Os objetos msm_qmp, qcom_aoss e qcom-ipcc
foram gerados; seus comandos registram `-flto`, CFI, SCS e reserva de x18.
Proveniência e hashes desses objetos foram preservados em
`private-diagnostics/qmp-audit/compiled-objects.json`. Isso não substitui
verificação do Image e dos símbolos finais após a ligação completa.

SHA-256 da configuração em uso:
`14be9f34ae437272b94ab884f373b385ac8e09e6bb2ab2297c9ae86f662075e4`.
O candidato publicado continua intocado. Ainda não há resultado final de build
ou execução no aparelho registrado nesta atualização.

## Atualização: configuração validada e compilação iniciada

O download terminou e ambas as revisões fixadas foram verificadas. Clang
Android 14.0.7 r450784e executou corretamente. O modo configure-only da receita
foi executado com sucesso em `.work/qmp-candidate-out/`.

Diff entre a configuração normalizada e a proposta QMP:

```text
MSM_QMP m -> y
QCOM_AOSS_QMP m -> y
```

CFI, CFI shadow, SCS, Full LTO, MODVERSIONS, MAILBOX, COMMON_CLK e PM passaram
pelas verificações da receita. Isso não significa que a normalização inteira
da configuração seja equivalente ao binário anterior. Os arquivos antes/depois
foram preservados para revisão.

Revisão adicional do diff entre ram-first.config e before-qmp.config: apenas
`CC_CAN_LINK=y` e `CC_CAN_LINK_STATIC=y` foram acrescentados por detecção do
compilador. Nenhuma outra mudança foi exibida nesse diff. Isso é comparação
de configuração, não prova de equivalência binária ao candidato publicado.

Há dois avisos de variáveis não usadas no lexer Kconfig gerado pelo flex do
host; não foram ocultados nem tratados como falha do kernel alvo.

Compilação `Image modules` iniciada separadamente em
`.work/qmp-candidate-build-out/`, com dois jobs e versão local
`-gd7102a837402-q3-ram-first-qmp`. **Resultado do build ainda pendente** neste
registro. Não publicar um Image parcial nem considerá-lo pronto para boot.

## Compatibilidade OpenSSL 4 do host

A primeira compilação parou em `scripts/extract-cert`: referências ENGINE
indefinidas ao ligar com OpenSSL 4. Nenhum Image completo foi produzido nessa
tentativa. O log original permanece em `build.log` na saída de build.

Patch revisado: `tools/patches/extract-cert-no-engine.patch`. Ele faz
extract-cert respeitar `OPENSSL_NO_ENGINE`, tal como sign-file já fazia.
Com `HOSTCFLAGS=-DOPENSSL_NO_ENGINE`, PKCS#11 ENGINE é recusado
explicitamente; extração de certificados PEM e assinatura por chave em arquivo
permanecem disponíveis. Essa opção afeta ferramentas do host, não CFI/SCS/LTO,
política de assinaturas do alvo ou verificações do kernel.

Verificações executadas com Clang fixado e OpenSSL do host:

- patch reversível contra a fonte esperada;
- compilação de extract-cert e sign-file;
- certificado PEM extraído igual ao DER gerado pelo OpenSSL;
- entrada vazia produz arquivo vazio;
- URI PKCS#11 recusada sem criar saída;
- assinatura de arquivo de teste com chave PEM gerada para o teste.

Arquivos e chave de teste temporários foram removidos ao terminar. Não houve
criação de chave operacional ou assinatura/instalação no Quest.

Para reproduzir em árvore limpa na revisão fixada:

```sh
git -C .work/kernel apply ../../tools/patches/extract-cert-no-engine.patch
Q3_HOST_NO_ENGINE=1 Q3_OUT="$PWD/.work/qmp-candidate-compatible-out" \
  bash tools/build-qmp-candidate.sh
```

A opção exige que a única diferença na árvore seja o arquivo extract-cert com
SHA-256 `28b8eb37b33dd372d2d189687b2edc6bec8660d784fc3fb9fc4425f295a4ea0b`.
Não é uma permissão genérica para builds com árvore alterada.

A primeira retomada usou HOST_EXTRACFLAGS, mas essa variável substituiu includes
específicos de subdiretórios e provocou erro classmap.h no gerador SELinux.
Essa tentativa não é válida; seu log foi preservado em build-openssl-compat.log.
A receita foi corrigida para HOSTCFLAGS, incorporada pelo Makefile sem substituir
os includes locais. Nova retomada incremental com versão/configuração preservadas
registra build-hostcflags.log. Resultado final ainda pendente neste registro.

## Validação preparada para os artefatos finais

Nova ferramenta `tools/verify-qmp-candidate.py`, somente host:

```sh
python3 tools/verify-qmp-candidate.py --out .work/qmp-candidate-build-out
```

Exige release separado, Image ARM64 com offset zero e limites da janela,
configurações/proteções requeridas, os dois drivers em modules.builtin,
flags CFI/SCS/LTO/x18 registradas nos comandos de compilação, símbolos QMP,
cabeçalho ELF64 ARM64 de vmlinux e Module.symvers não vazio. Isso verifica
consistência de artefatos; não autentica toda a execução do build, não valida
todos os CRCs, fluxo de máquina, dependências transitivas ou hardware.

Regressões sintéticas em `tools/test-qmp-candidate.py`, integradas à suíte:
25 testes aprovados, nenhum falhou/foi ignorado. O teste do corpo real qmp_open
é adicional e também passou. O verificador não foi aprovado contra um novo
Image real nesta etapa: a compilação ainda está em andamento.

## Teste host do handshake real

`quest3/qmp-audit/test-handshake.py` extrai da fonte fixada o corpo de
`qmp_open` e seus predicados, exige SHA-256 correspondente à auditoria e compila
essas funções contra mocks nativos de MMIO/esperas/doorbell. Passou em:

- estado inicial zerado e estado herdado UP simulado;
- magic, versão e tamanho inválidos sem escrita;
- sucesso do handshake e os três caminhos de timeout com limpeza.

```sh
python3 quest3/qmp-audit/test-handshake.py
```

Requer fonte pública preparada e compilador C host; não acessa o Quest.
É um teste adicional à suíte host principal, não uma validação de IRQs, barreiras,
tempos, acessos físicos ou firmware. Não implementa uma política de adoção.

## Estado registrado

- Dependências host encontradas: compiladores C/C++, make, cmake, flex, bison,
  bc, pkg-config e cross GCC ARM64; bibliotecas ELF/DWARF, compressão e OpenSSL.
- `pahole` adaptado compilado com sucesso em `.work/pahole-build/`.
- Download das fontes e toolchain fixadas iniciado por `tools/setup-sources.sh`.
  A conclusão e os builds seguintes devem ser registrados separadamente;
  iniciar o download não demonstra revisão disponível nem compilação do kernel.
- Receita nova: `tools/build-qmp-candidate.sh`; sintaxe bash verificada.
- Nenhum comando no aparelho realizado nesta etapa; Image publicado preservado.

Uma interrupção do primeiro fetch deixou um Git vazio. O helper agora permite
retomar somente repositório sem HEAD, sem arquivos de trabalho e com origin
igual ao esperado. Diretórios desconhecidos ou revisões diferentes continuam
recusados. Não houve reset/remoção de árvores existentes.

## Receita preparada

Depois de concluir a preparação das revisões e revisar fontes/ambiente:

```sh
bash tools/build-qmp-candidate.sh --configure-only
```

Por padrão produz `.work/qmp-candidate-out/` e recusa saída existente. O modo
configure-only não compila Image. Para uma compilação posterior, escolher uma
nova saída, sem apagar a anterior:

```sh
Q3_OUT="$PWD/.work/qmp-candidate-build-out" Q3_JOBS=2 \
  bash tools/build-qmp-candidate.sh
```

A receita guarda configuração anterior, diff QMP, versão do compilador,
revisão fonte, logs e hashes se o build completar. Ela exige QMP/AOSS embutidos
e preservação de CFI, SCS, Full LTO e MODVERSIONS. A checagem de árvore limpa
é intencional, com a exceção host exata documentada acima: patches adicionais
precisam revisão e registro antes de alterar essa política. A configuração
proposta não implementa adoção do link.

## Revisão do handshake

Na fonte pública, `qcom_aoss.c:qmp_open` valida magic/version/tamanho, publica
LINK_UP, espera ack, publica CH_UP e espera a abertura/ack remotos. Há três
esperas de até HZ ticks. Os caminhos de timeout publicam estados DOWN; portanto,
não é uma simples leitura passiva nem garantia de adoção de link herdado.
Essa sequência precisa de contrato específico para o handoff Anorak antes de
qualquer tentativa de salto. Built-in resolve disponibilidade, não esse contrato.

## Limites

A configuração já foi exercitada; o build completo permanece pendente nesta
atualização. GCC/bibliotecas recentes do host podem exigir correções de
compatibilidade, que devem ser documentadas sem desligar proteções do alvo.
Boot e retenção após reset permanecem não validados.
