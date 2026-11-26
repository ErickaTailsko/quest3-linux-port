# NDK r30 — download autorizado, verificado e preparado no projeto

> Continuação: [primeiro build ARM64/Bionic desarmado concluído](2026-11-17-cma-native-android-build.md).
> As referências abaixo a build pendente descrevem a etapa de preparação do NDK.

**NDK oficial disponível em `.work/android-ndk-r30/`.** Preparação restrita ao
host, autorizada pelo usuário. Sem instalação global, alteração persistente de
PATH/SDK, transferência ou operação no Quest. Ainda não foi feito build Android
do supervisor; o main e o controlador permanecem desarmados.

## Pacote e integridade

- Release LTS r30, revisão **30.0.16248370**.
- [Listagem oficial](https://developer.android.com/ndk/downloads).
- URL: `https://dl.google.com/android/repository/android-ndk-r30-linux.zip`.
- Tamanho baixado: **738.633.529 bytes**, igual ao publicado.
- SHA-1 publicado e conferido: `5107f898313790e449e87eee2183d9a20602dee9`.
- SHA-256 local registrado:
  `753611f410d002cfcd3f3dc2ef49aad532089d3180b436c060a90bf0fcb64df2`.

A página oficial publica SHA-1; o SHA-256 acima é a identidade local para
reconferências futuras, **não um SHA-256 independente publicado/verificado**.
O download usou HTTPS do domínio oficial. ZIP: CRC de todas as entradas passou;
10.134 entradas e 2.347.519.582 bytes descomprimidos. Caminhos e symlinks foram
checados para não escapar do diretório do pacote antes da extração.

O pacote foi extraído em staging novo, com espaço conferido e sem sobrescrever
árvore existente. source.properties confirma a revisão esperada; avisos/licenças
do pacote foram preservados. A página oficial/termos e os headers/logs do
download ficaram arquivados; não houve uso de sdkmanager nem modificação de
configuração global de licenças.

## Caminhos e smoke check

- NDK: `.work/android-ndk-r30/`.
- ZIP preservado: `.work/ndk-r30-download-01/android-ndk-r30-linux.zip`.
- Toolchain: `.work/android-ndk-r30/toolchains/llvm/prebuilt/linux-x86_64/`.
- Evidência privada: `private-diagnostics/ndk-r30-download-01/`.
- Metadados públicos: `quest3/toolchains/android-ndk-r30.json`.

O clang do pacote executou `--version` no host: Android Clang **21.0.0**, base
r574158c, build 16134705. Isso valida que a ferramenta host inicia, não um
executável Bionic nem funcionamento do supervisor no Android.

O sysroot declara fexecve como introduzido em API 28. Wrapper ARM64 API 28 e
stub libc correspondente existem. API 28 pode orientar o primeiro build mínimo,
mas **não é validação do API level/ABI runtime do Quest**. Esse vínculo e a
revisão de APIs/hardening continuam pendentes, sem nova consulta ao dispositivo.

## Preservações e próximo passo

Este NDK é candidato para o helper **userspace**, não substitui Clang Android
14.0.7 r450784e dos builds kernel/módulo. Não foram alterados tools/q3make,
Image, .ko, fonte do módulo, flags ou saídas anteriores.
O módulo da consulta conserva SHA-256
`21f62fad44c8ba33c3a16024d87f5c38406cfc20dd374643952b93578cfbd15e`.

A suíte host foi reconferida depois da preparação: **48 aprovações, zero falhas
e zero testes ignorados**. Nenhuma mudança de código foi necessária neste passo.

Próximo marco: build ARM64/Bionic separado do **main desarmado**, usando este
NDK explicitamente e verificando ELF, API, dependências e hardening, sem tratá-lo
como teste runtime. Dispatcher stock, catálogo/schema v2, reconciliação, ADB/su
e nova autorização específica de operação continuam gates independentes.
