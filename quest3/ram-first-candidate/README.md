# Quest 3 RAM-first: candidato de compilação, não pronto para boot

Release: 5.10.246-gd7102a837402-q3-ram-first.
Fonte pública sem modificações: facebookincubator/oculus-linux-kernel,
commit dbc2bc83a2b673f5d1c24ee9dadb0cd708ffda3f:
https://github.com/facebookincubator/oculus-linux-kernel/tree/dbc2bc83a2b673f5d1c24ee9dadb0cd708ffda3f
Toolchain Android clang/LLD r450784e 14.0.7, pahole 1.32 com correção CFI
já usada na sessão. Full LTO e META_SAMPLE_PGO mantidos. Fonte do kernel
permanece limpa; mudanças somente no .config isolado.

39 ajustes solicitados, 38 mudanças efetivas n/m -> y. 33 módulos/provedores
da cadeia USB analisada agora constam em modules.builtin. Inclui controlador,
PHYs, reguladores, GCC/RPMh, pinctrl, interconnect, SMMU e UCSI/PMIC GLINK.
DEVTMPFS e os requisitos básicos do initramfs também embutidos.
Compilação Image código 0, sem warnings. BTFIDS/SORTTAB/SYSMAP concluídos;
bpftool decodificou BTF, inclusive vfs_truncate. CFI/SCS nos comandos USB,
sem símbolos fortes indefinidos. Três símbolos EFI fracos opcionais mantidos.

Initramfs correspondente: BusyBox estático ARM64, ECM, sem discos montados.
SHA no manifesto vincula o kernel a esse artefato, mas não prova compatibilidade
em execução. Não inclui DTB, módulos externos nem imagem boot/vendor_boot.
Não contém diagnósticos ou o Device Tree enviados pelo usuário.

Pendências: UCSI requer transporte/serviço PMIC_RTR_ADSP_APPS no ADSP; o
initramfs não inclui adsp.mdt e reaproveitamento do serviço não foi validado.
Configuração e link não provam probe, enumeração USB ou parada de DMA.
Faltam handoff CFI, revisão de estado herdado/DT e captura de log confiável.
Os testes pstore/pmsg no reboot stock não recuperaram os marcadores.
Não inicializado no Quest. boot_ready=false.

O módulo quest_kexec que passou no preflight continua compilado contra stock;
NÃO carregar os módulos stock como se fossem módulos desta nova release.
Não é pacote de flash. Nenhuma instrução de boot/reset é fornecida.

Para reproduzir só a configuração, com q3make já definido no computador:
  python3 apply-fragment.py --base ~/quest3-llvm-config.bOyxO7/.config --out /CAMINHO/NOVO_OUT/.config
  q3make O=/CAMINHO/NOVO_OUT LOCALVERSION=-gd7102a837402-q3-ram-first olddefconfig
  q3make -j4 O=/CAMINHO/NOVO_OUT LOCALVERSION=-gd7102a837402-q3-ram-first Image
O diretório de saída deve ser novo e absoluto, separado de stock.

Para conferir a transferência:
  sha256sum -c SHA256SUMS
