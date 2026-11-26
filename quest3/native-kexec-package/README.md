# Kernel nativo experimental, não instalado

Release: 5.10.246-gd7102a837402-qkx-native-probe

Image ARM64 e 272 módulos desta mesma compilação. CFI/SCS/Full LTO preservados. As únicas mudanças de configuração são KEXEC/KEXEC_CORE/CRASH_CORE. Há 12 CRCs exportados diferentes do conjunto stock; não misture módulos dos dois conjuntos.

O kernel completo e os módulos passaram por compilação e verificação de BTF/CRC/CFI. Não há boot.img, vendor_boot, DTBO, initramfs do aparelho ou validação da cadeia de boot neste pacote. Não foi instalado, inicializado nem usado para executar kexec no Quest. O suporte nativo oferece uma alternativa de integração, mas não comprova que os drivers da placa realizam todo o desligamento exigido.

Consulte native-kexec-plan.md e CHECKLIST.md. O acesso root confirmado não confirma, por si só, um método seguro/funcional para iniciar ou recuperar este kernel.
