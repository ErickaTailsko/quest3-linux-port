# Core-hang: suporte ao formato de arrays do Device Tree

Módulos stock para 5.10.246-gd7102a837402, com CFI/SCS/Full LTO preservados. Inclui as correções anteriores.

O parser aceita dois esquemas. Se qcom,chd-percpu-info existir, permanece a validação de phandles. Se estiver ausente, qcom,config-arr e qcom,threshold-arr são validados: mesmo número de entradas, cobertura do número de CPUs possíveis, limites, alinhamento, valores não nulos e configurações sem duplicação. Toda validação ocorre antes do primeiro acesso SCM. Propriedade phandle presente mas malformada não provoca fallback silencioso.

No esquema de arrays, core_hang_control=1 usa qcom_scm_io_readl e identifica entradas pelo índice da lista, sem supor correspondência com CPU lógica. core_hang_control=2 é recusado com -EOPNOTSUPP antes de leituras/escritas: o DT fornece endereços, não confirma o contrato dos bits de escrita do driver correspondente. Não existe fallback para endereços fixos.

O preflight independente continua sem operações de hardware: preflight_only=1 execute=0, sem outros controles. core_hang_control no fluxo normal só é processado depois do staging. Execução kexec, ensaios 2/3, CPU, warm reset e usb_log continuam bloqueados sob CFI.

Validação: compilação sem erros/avisos novos; CRCs/CFI/SCS/BTF aprovados. Testes do fonte de produção usam dados sintéticos, cobrem ambos os esquemas, seis entradas, propriedades inválidas, falhas de leitura, limpeza de referências e rejeição de escrita no formato de arrays. Não houve carga nem acesso SCM no aparelho a partir deste ambiente.

O pacote contém fontes, módulos, patch incremental sobre local-complete e logs de compilação/testes. Não contém diagnósticos, Device Tree nem lista de módulos enviados pelo usuário, e não contém o kernel experimental.
