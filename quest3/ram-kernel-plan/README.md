# Kernel de primeiro alvo RAM — configuração isolada

Base: kernel stock preparado, não altera out/ nem o módulo validado no aparelho.
Saída: ram-first-kernel; release pretendida 5.10.246-gd7102a837402-q3-ram-first.
usb-builtin.fragment seleciona DEVTMPFS e provedores USB do DT real + imports
transitivos dos módulos do kernel experimental anterior. 39 opções =y.
Kconfig aceitou o fragmento; CFI/SCS/Full LTO/MODVERSIONS preservados.

Dependências: DWC3 MSM, PHY HS/SS, GCC, RPMh, GDSC/reguladores, pinctrl,
interconnect, SMMU, UCSI e PMIC GLINK/QMI/PDR. As referências DT analisadas
incluem clocks/resets/supplies/iommus/pinctrl/interconnects e grafo do conector.
Aliases OF ausentes são complementados explicitamente por exame do fonte:
rpmh_regulator, gcc_anorak, gdsc_regulator e ucsi_glink. O grafo não resolve
protocolos firmware nem referências implícitas por strings.

UCSI comunica com PMIC GLINK por PMIC_RTR_ADSP_APPS. No DT este canal está sob
remoteproc ADSP; o driver PAS anorak configura adsp.mdt e auto_boot=false.
O initramfs não contém esse firmware nem carrega o driver PAS. Embutir UCSI
não comprova que exista o transporte/firmware após o handoff. Não acrescentar
autoboot/reautenticação de ADSP sem avaliar o firmware herdado. Papel USB fixo
ou controle de papel pelo sysfs são alternativas a revisar, não habilitadas.

Sem patches de kexec/handoff neste fonte, sem endereços novos de staging,
sem reset, flash ou execução no Quest. Core-hang DT e retenção de log pendentes.
Mesmo um Image linkado com sucesso é apenas candidato de compilação.
Não usar módulos stock com release/CRCs deste novo kernel.

## Reproduzir a configuração no computador do usuário
Com os scripts deste diretório e o q3make já usado na sessão:
  python3 apply-fragment.py --base ~/quest3-llvm-config.bOyxO7/.config --out NOVO_OUT/.config
  q3make O=NOVO_OUT LOCALVERSION=-gd7102a837402-q3-ram-first olddefconfig
  q3make -j4 O=NOVO_OUT LOCALVERSION=-gd7102a837402-q3-ram-first Image
Usar NOVO_OUT absoluto e diferente do diretório stock. Não carregar módulos
externos compilados contra esse diretório no Android stock. Não é instrução
para iniciar Image nem para escrever boot/vendor_boot.

As linhas '# ... is not set' adicionais para ARM_SMMU_LEGACY_DT_BINDINGS,
QCOM_IOMMU e MSM_JTAGV8 são opções que ficaram visíveis com as dependências
novas, mas continuam desativadas. verify-config.py compara valores efetivos,
tratando opções ausentes como n, para não descrevê-las como drivers removidos.
