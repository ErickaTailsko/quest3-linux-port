# Bootstrap ARM64/Bionic API28 — build separado e desarmado

**Dois artefatos compilados e verificados offline; nenhum executado ou enviado
ao Android.** A suíte completa aprovou **53 grupos**, sem falhas ou ignorados.
O controlador continua desarmado, sem transporte live ou admissão de ações.

## Artefatos e proveniência

Fontes `bootstrap.c` e `sha256.h` foram copiados para
`.work/cma-bootstrap-android-build-01/source/`, sem alterar o supervisor anterior.
Foi usado o NDK r30 `30.0.16248370` previamente verificado e instalado localmente,
Clang 21, target `aarch64-linux-android28` e sysroot Bionic. API28 é um alvo de
compilação, não uma checagem da API/runtime do Quest.

| Variante | Bytes | SHA-256 |
|---|---:|---|
| disarmed | 5.608 | `a16d6e90f48883cddca6c95241bafeaab2b15c9d2db8483b1703effe428270b4` |
| core-linkcheck-disarmed | 17.688 | `ee42ade810274c5080533907d860cd5f17c9d9d3dee23a3640fc05d86f116ba9` |

O binário mínimo tem o mesmo hash do main desarmado do supervisor anterior:
o linker elimina o núcleo não referenciado e mantém a mesma mensagem/retorno.
É um arquivo novo em diretório separado, não uma substituição do anterior.
A segunda variante retém `q3_bootstrap_metadata_reference` por
`-Wl,--undefined=q3_bootstrap_metadata_reference`, para resolver e inspecionar
suas dependências. **Reter o núcleo não o conecta ao main nem o ativa.**

Ambos usam Full LTO, visibilidade hidden, flags CFI/trap, stack protector strong,
FORTIFY=2, x18 reservado, PIE, RELRO/NOW e stack não executável. Não foi habilitado
SCS de userspace sem runtime revisado. Kernel/módulo mantêm seus próprios
CFI/SCS/LTO/MODVERSIONS, sem alteração de configuração ou rebuild nesta etapa.

## Verificação offline

`verify-bootstrap-android.py` reutiliza o leitor ELF já testado do supervisor e
adiciona o perfil específico do bootstrap. Confere:

- ELF64 AArch64 ET_DYN, `/system/bin/linker64`, nota API28/NDK r30;
- dependências somente `libc.so` e `libdl.so`, PIE/NOW/RELRO, sem TEXTREL,
  stack executável ou segmentos simultaneamente graváveis/executáveis;
- alinhamentos LOAD de 16 KiB nos artefatos produzidos;
- ausência dos marcadores de CLI/hooks `Q3_BOOTSTRAP_HOST_TEST` nos bytes
  relevantes: `--host-bootstrap`, `Q3_BOOTSTRAP_FAULT`, `Q3_BOOTSTRAP_PAUSE`;
- lista exata de imports registrados, com versões LIBC no mínimo e LIBC/LIBC_N
  no núcleo retido, sem GLIBC ou APIs de execução de processos/módulos;
- disassembly registrado do main com somente chamada a write e retorno 77;
- objeto primário em bitcode LLVM e metadados CFI na definição do núcleo no IR
  prelink registrado, além de flags, hashes e proveniência dos fontes.

LLVM adicionou `range(i32 0, 78)` ao retorno da função no IR otimizado. O parser
aceita essa forma observada e a forma sem atributo; os testes exigem que o
metadado `!type` esteja na definição da função, não apenas em outra linha.

Relatórios LLVM e argv são evidências locais registradas, não uma atestação
criptográfica de origem. Flags/metadados CFI **não comprovam enforcement em
runtime**, em particular em um núcleo sem dispatcher live. O main foi
inspecionado, não executado por emulador nem pelo Android.

Reverificação:

```sh
python3 quest3/cma-identity-query/native-supervisor/verify-bootstrap-android.py \
  --out .work/cma-bootstrap-android-build-01 \
  --archive private-diagnostics/cma-bootstrap-android-build-01
python3 quest3/cma-identity-query/native-supervisor/test-bootstrap-android-verifier.py
```

Resultado público: `native-supervisor/bootstrap-android-build-verification.json`.
Comandos, logs, fontes, bitcode, mapas, cópias dos ELFs, relatórios LLVM, suíte e
hashes estão preservados em `private-diagnostics/cma-bootstrap-android-build-01/`.
O verificador do supervisor anterior não foi modificado. Fontes e dois ELFs
anteriores, módulo de identidade e Image trim3 foram reconferidos por hash.

## Limites e próximo gate

Este build continua sendo a referência **somente de metadados** descrita no
[resultado host](2026-11-17-cma-native-bootstrap-host.md). Não valida identidade
real do dispositivo/boot, autorização, pai confiável em produção, ABI/runtime,
filesystem, durabilidade após power-loss ou SELinux no Quest.

Próximo gate host: contrato e testes do ACK local durável/importação explícita de
pins, sem ativar o writer. A leitura de recibo ou uma resposta coincidente não
podem, por si, converter pins candidatos em admissão. Journal incerto continua
congelando comandos; observação não libera retry, takeover, cleanup ou replay.
Writer sequencial de produção, dispatcher, integração e nova autorização para
qualquer operação no dispositivo continuam pendentes. Não houve aquisição de RAM,
inserção de módulo ou tentativa de boot/handoff.
