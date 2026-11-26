# SCM e Device Tree — Quest 3

Módulos recompilados para 5.10.246-gd7102a837402 com Clang 14.0.7, Full LTO, CFI e Shadow Call Stack. Inclui as correções anteriores de x18 e bloqueios de símbolos privados.

## Implementação

- quest3-scm.c usa linux/qcom_scm.h e as APIs exportadas qcom_scm_is_available, qcom_scm_io_readl, qcom_scm_io_writel e qcom_scm_sec_wdog_deactivate. Não depende de soc/qcom/scm.h nem procura símbolos SCM via kallsyms.
- O nó ativo qcom,core-hang-detect fornece qcom,chd-percpu-info: cada entrada tem phandle de CPU, endereço de threshold e endereço de configuração. Apenas o segundo argumento é acessado. Não há fallback para endereços fixos.
- Valida formato, cobertura dos CPUs possíveis, duplicação de CPUs/endereços, alinhamento e endereço não nulo antes do primeiro acesso SCM. Referências DT são liberadas em todos os caminhos.
- core_hang_control=0 não altera nada; 1 apenas lê; 2 limpa somente BIT(1), verifica o valor completo e tenta restaurar os registradores alterados se a própria operação falhar. Falha de restauração é registrada e o erro original é preservado.
- secure_watchdog_control=1 informa somente prontidão do driver SCM; não confirma suporte do firmware ao comando. O modo 2 chama a função oficial uma vez e propaga o retorno, sem sondar assinaturas alternativas. O driver define o ABI e os argumentos do comando, portanto não há endereço DT para essa chamada.

## Limites atuais

Os controles SCM agora funcionam sem o resolvedor privado sob CFI. execute/preflight, test_cpus, warm_reset_test e usb_log continuam recusados sob CFI. As adaptações de USB e watchdog não seguro ainda estão pendentes.

Os controles SCM continuam sendo aplicados antes do staging, como na versão anterior. Uma alteração bem-sucedida não é desfeita automaticamente se uma etapa posterior falhar ou se o módulo for descarregado. A API de desativação do watchdog seguro não oferece operação inversa neste código. O rollback implementado cobre falhas dentro da operação core-hang; não é uma transação entre todos os parâmetros.

## Validação

Compilação: saída 0, sem avisos novos. CRCs dos módulos, configuração, CFI/SCS e BTF aprovados. Inspeção dos binários confirma os imports qcom_scm e ausência do resolvedor/kprobes. Testes host usam o código SCM de produção com DT/firmware simulados e injeção de erros, incluindo readback divergente e falha de rollback. ASan/UBSan ativos; LeakSanitizer desativado porque este ambiente usa ptrace. Nenhum módulo foi carregado no headset; aceitação dos comandos pelo firmware e endereços do DT real ainda precisam de validação no aparelho.

## Aplicação

Use apenas um patch na raiz do quest-kexec: from-cfi-guard.patch para a versão do pacote anterior, ou from-original.patch para os fontes originais enviados. A pasta module contém os fontes completos usados nesta compilação e os três módulos resultantes. As ferramentas de build/verificação mantêm os caminhos do workspace /workspace/quest3-build; toolchain e árvore do kernel não estão incluídos.
