# Correção CFI e x18

Compilado para 5.10.246-gd7102a837402 com Clang 14.0.7, Full LTO, CFI e Shadow Call Stack mantidos.

Sob CONFIG_CFI_CLANG, quest_kexec retorna -EOPNOTSUPP para execute=1 (inclusive preflight_only=1/2/3), test_cpus=1/2, warm_reset_test=1, core_hang_control=1/2 e secure_watchdog_control=1/2. Combinações inválidas de parâmetros continuam retornando -EINVAL. A rejeição acontece antes de sondar kallsyms, alterar hardware ou preparar arquivos/memória de staging. O teste de compatibilidade da placa ainda pode retornar -ENODEV primeiro.

usb_log é recusado com -EOPNOTSUPP sob CFI, antes de registrar kprobe, console ou hook USB. Os caminhos legados permanecem no fonte para builds sem CFI; isso não valida seu funcionamento nesse modo.

O staging usa walk_iomem_res_desc exportado, com os mesmos flags e intervalo de walk_system_ram_res. test_transition e test_full_copy não dependem do resolvedor privado e continuam disponíveis; não foram validados no aparelho. marker_read não mudou.

qkx_roundtrip salva/restaura x18 junto com x30 no offset 80; o frame continua tendo 96 bytes. A inspeção do binário confirmou as instruções correspondentes.

Verificação: compilação dos módulos com saída 0; verificações existentes de config, CRC, CFI/SCS e BTF aprovadas; verificação adicional compara os módulos originais com os corrigidos e confirma a remoção do resolvedor/kprobes nos binários CFI. Não houve carregamento nem teste de MMU no dispositivo.

Aplicar cfi-x18.patch com `git apply` na raiz do quest-kexec correspondente ao fonte original enviado. A validação verify-cfi-guards.py é executada na raiz do workspace quest3-build, onde estão toolchain, entradas originais e módulos.

As adaptações completas SCM/USB/watchdog continuam pendentes; estes bloqueios não são uma implementação do salto kexec no Quest 3. Os arquivos experimentais quest3-platform não estão integrados e não fazem parte deste pacote.
