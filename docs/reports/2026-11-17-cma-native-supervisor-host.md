# Consulta CMA — núcleo supervisor C testado no host, ainda sem build Android

> Atualização posterior: [NDK r30 baixado e verificado com autorização](2026-11-17-android-ndk-r30-preparation.md).
> A ausência de NDK mencionada abaixo registra a etapa anterior. O
> [build ARM64/Bionic desarmado](2026-11-17-cma-native-android-build.md) também
> foi concluído depois. Runtime Android e implantação continuam pendentes.

**Núcleo nativo de execução/recibo implementado e testado com fixtures locais.**
O executável padrão é desarmado; somente o build de teste pode despachar uma
fixture. Não houve ADB, transferência, carga de módulo, operação no Quest ou
aquisição de payload. O controlador permanece com EXPECTED_MODULE=None e sem
integração com este núcleo.

## O que foi construído

Novo diretório `quest3/cma-identity-query/native-supervisor/`:

- supervisor.c: core single-threaded de fork/captura/wait/publicação; main
  padrão retorna 77 sem iniciar ação ou abrir o store;
- sha256.h: SHA-256 pequeno para hashes não autenticados, comparado com hashlib;
- native_receipt.py: parser bounded do resultado v2, sem I/O, retomada ou cleanup;
- test-supervisor.py: compila o main desarmado, core de teste e fixtures benignas
  do host, sem shell action ou syscalls de módulo.

Builds arquivados usam GCC do host, -Wall/-Wextra/-Werror, -flto, PIE,
stack-protector-strong, FORTIFY_SOURCE=2 e RELRO/NOW. O main desarmado foi
executado e recusou o modo fixture com retorno 77. Hashes, compilador e flags
reais estão em `quest3/cma-identity-query/native-supervisor/host-build-verification.json`.
Essas flags do host **não são evidência de CFI/SCS Android**.

Não foi localizado NDK na preparação .work do projeto, nem selecionado um sysroot
Android/Bionic verificado para este build. Não se substituiu isso por libc GNU
cross-compilada nem se declarou um ELF host como binário Android. A validação
de target, API de Bionic (incluindo fexecve), headers/CRT e hardening permanece
pendente. Nenhum SDK/NDK foi instalado ou baixado nesta etapa.

## Contrato exercitado

1. O caller de teste obtém uma claim durável da referência filesystem e passa
   FDs de diretório, lease e ELF de fixture, com identidade previamente fixada.
2. O core confere diretório/lease/owner/claim e rejeita symlinks/substituições
   observadas, permissão/dono inconsistentes e entradas extras. Deliberadamente
   aceita somente **uma operação por diretório** neste estágio: não há migração
   de catálogo ou retirement nativo.
3. O ELF aberto e o modo de fixture são vinculados ao action_sha256 de domínio
   host-fixture-v1. Isso é um protocolo de teste, não a ABI de ações stock.
4. O core faz um único fork, preserva a mesma open-file-description da lease,
   fecha FDs não permitidos no filho e usa fexecve com ambiente mínimo, sem shell.
5. Captura stdout e stderr separadamente, até 64 KiB cada. Continua drenando
   após overflow para não confundir backpressure com término, mas não publica
   resultado truncado como sucesso.
6. Espera EOF e depois **waitpid do PID exato**, repetindo wait/poll apenas em
   EINTR. EOF precoce não vence o wait: uma fixture fecha ambos os streams e
   continua bloqueada, sem que apareça recibo prematuro.
7. Depois de reap, publica recibo imutável por staging exclusivo, fsync do
   arquivo, link sem overwrite e fsync/retirada de staging/fsync do diretório.
   Só então escreve ERIS_NATIVE_RECEIPT com o nonce da operação.

A resposta confirma publicação do supervisor, **não exit zero da ação**.
Um comando que saiu com 23 ou 127 pode ter um recibo válido; não é uma consulta
de identidade aprovada por esse motivo. Erro de exec é registrado separadamente
da saída normal 127. Um retorno 74 do supervisor pode deixar claim/staging ou
um recibo já publicado cuja resposta se perdeu; não concede retry.

## Sinais e lease

INT/TERM/HUP no supervisor são registrados sem matar/reenviar o sinal ao filho;
o core continua aguardando/capturando. SIGPIPE na resposta é ignorado para que
não se perca a evidência já persistida. O filho restaura disposições normais
antes de exec. O núcleo não implementa deadline interno, kill de timeout, reboot,
LOCK_UN ou liberação forçada da lease.

O teste de SIGKILL mata somente o supervisor de fixture conhecido. O filho ainda
mantém o fd e a observação retorna lease-held. Após liberar e confirmar saída
do filho via pidfd do host, sobra claim-without-receipt, não um sucesso inferido.
Não se usou PID desaparecido, delay ou amostras de ausência como quiescência.

Isso demonstra propriedades de processos/FDs no Linux **do host**, não de
ADB/su, Android, kernel module init ou processos/trabalhos arbitrários. O núcleo
é single-threaded; não deve ser chamado dentro de um host multithreaded sem
revisar as operações pós-fork.

## Recibo v2 e recuperação

O recibo inclui Intent completa, foreground_reaped, tipo/valor de término
(exit versus signal), errno de exec, sinal observado pelo supervisor e ambos
os streams com base64/tamanho/SHA-256. Os campos tree_quiescence_proven e
safe_to_mutate são fixados falsos.

O parser também mantém lease_free_verified, automatic_resume_allowed e boot_ready
falsos: ele recebe bytes e não observa diretório, lease ou boot. O recibo v2
é **intencionalmente incompatível** com o ledger v1; o teste verifica que a
referência antiga retorna unknown, sem migrar, liberar próxima ação ou retomar.
O framing atual do controlador não foi substituído pelo ACK nativo.

Nenhum recibo recuperado limpa o journal antigo, inicia rmmod/rm ou repete
insmod. Falta a camada revisada de observação no boot correto e de decisão
separada sobre os objetos desta tentativa.

## Testes e evidências

Suíte completa: **48 aprovações, zero falhas e zero testes ignorados**.
O novo teste compila e executa C real e cobre:

- default desarmado, saída normal/não zero, saída binária e FDs não permitidos;
- SHA-256 em limites de bloco/padding e 64 KiB contra Python hashlib;
- falha de exec distinta de exit 127, término por sinal e sinal no supervisor;
- wait após fechamento precoce de streams, perda da resposta depois do recibo;
- SIGKILL com lease herdada, rejeição de replay/claim/hash divergentes;
- overflow e colisão de staging, além de hooks test-only de falha em
  fsync/link/unlink, sem ACK falso ou overwrite de evidência.

Hooks de sinal/sincronização e fault injection só existem no build host-test;
não são opções de uma interface de produção. Os testes não simulam power-loss
real nem validam semântica de filesystem/SELinux no dispositivo.

Fontes, executáveis host (desarmado e teste, **não distribuíveis como helper de
dispositivo**), logs de compilação e suíte ficam arquivados com hashes em
`private-diagnostics/cma-native-supervisor-01/`.
O .ko da consulta continua com SHA-256
`21f62fad44c8ba33c3a16024d87f5c38406cfc20dd374643952b93578cfbd15e`;
fonte C do módulo, Image e proteções kernel não foram alterados.

## Próximos gates, sem implantação implícita

1. Preparar toolchain/sysroot Android verificável e compilar o main desarmado
   para Bionic, revisando APIs, ABI e hardening do target.
2. Implementar/revisar dispatcher de ações fixas e boot atual: esta fixture
   apenas compara o UUID solicitado com a claim; não valida boot real do Quest.
   Não há syscall de módulo, política de comando stock ou inicialização nativa
   do ledger nesta etapa.
3. Fixar raiz canônica/lease global e proteção de inode/conteúdo do módulo;
   hashes/dir-fd não impedem outro root não cooperante nem resolvem todos TOCTOU.
4. Revisar schema v2, catálogo sequencial, observador de recuperação sem replay,
   filesystem/SELinux stock e adaptador ADB/su limitado.
5. Só depois considerar nova autorização específica. Não habilitar hash de
   implantação, transferir helper ou consultar CMA pelo simples sucesso host.
