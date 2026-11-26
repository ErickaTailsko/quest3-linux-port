# Caminho nativo de kexec: alcance e limites

A configuração do kernel atualmente reproduzido tem CONFIG_KEXEC=n e CONFIG_KEXEC_FILE=n. Seu Module.symvers não exporta as interfaces de freezer/desligamento/CPUs ainda utilizadas pelo módulo experimental. Por isso, as correções locais não autorizam remover os bloqueios de execução.

A árvore ARM64 contém o caminho nativo: CONFIG_KEXEC depende de PM_SLEEP_SMP, seleciona KEXEC_CORE e compila machine_kexec/relocate_kernel e a syscall kexec_load. A configuração isolada habilita somente KEXEC e suas dependências KEXEC_CORE/CRASH_CORE. CFI, SCS, Full LTO, MODVERSIONS e PGO permanecem ativos. A versão recebe o sufixo -qkx-native-probe para evitar confusão com o kernel do aparelho.

Os arquivos ficam em native-kexec-probe; os artefatos stock em out permanecem separados. O kernel experimental não torna o módulo stock capaz de chamar símbolos privados. A alternativa é inicializar um kernel com suporte nativo e usar a interface nativa, após validar as particularidades da placa.

Antes de usar esse kernel no Quest, é necessário verificar no aparelho a cadeia de boot e recuperação disponível, formato de boot/vendor_boot, DTB/DTBO, módulos externos/vendor, firmware e requisitos de assinatura. Nenhum boot.img foi montado, nenhuma partição foi escrita e nenhum comando de reboot/kexec foi executado nesta sessão.

A compilação comprova que o código liga com essa configuração. Não comprova que USB, GPU, DSP, sensores, DMA, watchdog, Gunyah ou todos os núcleos chegam ao estado necessário para o salto. O desligamento nativo e a inicialização do destino precisam ser validados no hardware, com captura de logs e recuperação verificadas primeiro.

Sequência posterior: coletar estado atual; validar preflight/staging do módulo compatível; verificar boot e recuperação; preparar uma imagem de boot compatível com os dados reais; inicializar e conferir a versão experimental; validar módulos e drivers; só então testar carregamento e execução nativa de um kernel destino. Os tempos/regras de watchdog e a comunicação QMP continuam sujeitos à validação da plataforma.

## Achado do Device Tree real

A coleta posterior confirmou o formato qcom,config-arr/qcom,threshold-arr, enquanto o driver core_hang_detect da árvore pública compilada espera qcom,chd-percpu-info. O kernel experimental já compilado ainda precisa dessa adaptação ou de uma combinação kernel/DT validada. A compilação bem-sucedida não resolve essa divergência; não tratá-lo como pronto para boot. O módulo stock recebeu suporte de leitura ao formato de arrays, com escrita bloqueada até confirmar o contrato do driver real.
