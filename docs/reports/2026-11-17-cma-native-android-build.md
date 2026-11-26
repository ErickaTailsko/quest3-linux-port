# Supervisor — primeiro build ARM64/Bionic verificado, main desarmado

> Continuação: [revisão de bootstrap/catálogo e observador v2 no host](2026-11-17-cma-v2-catalog-bootstrap-review.md).
> Os ELFs deste build permanecem iguais. Observação explícita não libera
> admissão, migração do ledger ou operação no Quest.

**Dois artefatos Android compilados e verificados somente por arquivos no host.**
Nenhum executável ARM64 foi iniciado, emulador usado, arquivo transferido ou
operação feita no Quest. Dispatcher de produção e controlador continuam
desabilitados. Não é build de kernel nem tentativa de boot.

## Artefatos

| Variante | Bytes | Finalidade |
|---|---:|---|
| disarmed | 5.608 | Main mínimo que escreve a mensagem de bloqueio e retorna 77 |
| core-linkcheck-disarmed | 23.576 | Mesmo main, retendo o núcleo por raiz de link para conferir APIs/imports |

SHA-256 do mínimo:
`a16d6e90f48883cddca6c95241bafeaab2b15c9d2db8483b1703effe428270b4`.
SHA-256 do linkcheck:
`bb9ea578412b9293c92222869674d7710e5aa9d715e24ffaa8abbfb7ba02fcd4`.

Fontes copiados, sem alterações, para saída nova
`.work/cma-native-android-build-01/`. NDK r30/30.0.16248370, Clang 21.0.0,
target `aarch64-linux-android28`, sysroot explicitamente o do NDK preparado.
Ambas as compilações terminaram com retorno zero; não houve relaxamento de
warnings, fallback para GNU libc ou definição de Q3_SUPERVISOR_HOST_TEST.

O linkcheck usa `-Wl,--undefined=q3_supervise_fixture` para impedir que LTO/GC
removam a função não chamada. Sem isso, o executável mínimo não demonstraria
que os imports do núcleo resolvem em Bionic. **Reter código não o torna
alcançável por uma interface de comandos**: o main continua sendo o desarmado.
Não se afirma reprodutibilidade binária a partir de um único build por perfil.

## ELF, ABI de build e dependências

O novo `native-supervisor/verify-android-build.py` confere bytes de ELF e
relatórios LLVM registrados, sem executar artefatos:

- ELF64 little-endian AArch64, ET_DYN/PIE, entrada em LOAD executável;
- interpretador `/system/bin/linker64`, não linker GNU do host;
- somente `libc.so` e `libdl.so` em DT_NEEDED, sem RPATH/RUNPATH;
- nota Android API **28**, NDK r30/build 16248370;
- segmentos LOAD alinhados em 16 KiB; nenhum LOAD W+X, stack não executável,
  GNU_RELRO presente e BIND_NOW/PIE marcados, sem TEXTREL;
- versões Bionic LIBC no mínimo e LIBC/LIBC_N/LIBC_P no núcleo;
- 2 imports do mínimo; 48 imports do núcleo, em allowlist fixa. Incluem
  fexecve, fork, waitpid, flock, fsync e funções fortificadas. Não há import de
  syscalls de módulo, system, shell dispatcher ou hooks de teste.

API 28 foi escolhida como mínimo de build, coerente com fexecve nos headers
e stubs do NDK. **Não é leitura/validação do SDK level ou linker do Quest.**
Compatibilidade runtime, regras de namespace/SELinux, filesystem e execução
continuam não demonstradas. O alinhamento ELF de 16 KiB não muda requisitos
do Image ARM64 nem constitui escolha de destino CMA.

## Main e proteções

O disassembly registrado de ambos os mains mostra um único BL para write,
seguido de `mov w0, #77`, restauração do frame e retorno. Não há chamada ao
núcleo nesse trecho. A mensagem desarmada está nos dois ELF; marcadores de CLI
host-test e Q3_NATIVE_FAULT estão ausentes. Isso é inspeção estática, não um
retorno 77 observado executando Android.

Flags conferidas: Full LTO (`-flto=full`), CFI local em modo trap,
visibility hidden, stack-protector-strong, FORTIFY_SOURCE=2, x18 reservado,
PIE, RELRO/NOW, noexecstack, no-undefined e fatal-warnings. Objetos de entrada
são bitcode LLVM e o IR pré-link contém o núcleo e metadados CFI `!type`.
O núcleo retido importa __stack_chk_fail e wrappers fortificados Bionic.

**CFI runtime não foi validado.** Metadados/flags não demonstram todos os
caminhos e LTO pode eliminar checks sem sites indiretos aplicáveis. Não se
confunde esse CFI userspace com o contrato cross-DSO do módulo/kernel.

**SCS não foi ativado no helper userspace:** não há inicialização/alocação de
shadow stack ou runtime revisado para ele. Reservar x18 não implementa SCS;
transplantar flags do kernel poderia produzir um helper inválido. CFI/SCS/Full
LTO/MODVERSIONS dos candidatos kernel e módulo não foram alterados. A definição
do hardening do dispatcher futuro permanece gate próprio.

## Evidências e testes

Resultado público: `quest3/cma-identity-query/native-supervisor/android-build-verification.json`.
Intenção, comandos exatos, logs, ELF, nm, versões, disassembly, IR e cópias
de binários/objetos/preprocessado/maps estão preservados com hashes em
`private-diagnostics/cma-native-android-build-01/`. Binários ativos não foram
distribuídos e nenhum hook host-test foi compilado nesses artefatos Android.

`test-android-verifier.py` acrescenta fixtures **sintéticas**, sem NDK, para
ELF truncado/arquitetura errada, API/NDK/interpreter/dependências divergentes,
flags PIE/NOW/stack/RELRO, import fora da lista, main que não retorna 77,
CFI metadata ausente e flags conflitantes/hook de teste. Não executa Android.

Suíte completa: **49 aprovações, zero falhas e zero testes ignorados**.
SHA-256 reconferidos sem mudança: módulo de identidade
`21f62fad44c8ba33c3a16024d87f5c38406cfc20dd374643952b93578cfbd15e` e
Image trim3 `215c0baf386deb0dc7f8f584dae0ce8bd757b8fb4055482c9942c1fe4c99c5f4`.

## Gates seguintes

O primeiro build Bionic desarmado está concluído; **nenhum gate de dispositivo
foi consumido/encerrado**. Continuam pendentes dispatcher de ações fixas,
bootstrap/catálogo nativos, raiz/lease canônicas, revisão de schema v2 e
observação de recuperação sem replay. O parser atual e o ledger v1 não passam
a migrar recibos ou retomar transações por causa deste build.

Antes de uso live: revisar ABI/SDK e hardening aplicáveis, integração com
filesystem/SELinux stock e adaptador ADB/su limitado. Depois disso, eventual
consulta requer autorização específica. Não habilitar hash de implantação,
transferir artefatos, chamar alocadores ou iniciar handoff automaticamente.
