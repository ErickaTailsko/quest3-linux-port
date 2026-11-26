# USB e watchdog — Quest 3

Fontes integrados e módulos recompilados para 5.10.246-gd7102a837402, com Clang 14.0.7, Full LTO, CFI e Shadow Call Stack. Inclui as correções anteriores de x18 e SCM/Device Tree.

## USB

Usa usb_gadget_disconnect/connect, deixando o runtime PM para o driver DWC3 deste kernel. Remove o acesso presumido a in_lpm e a chamada privada dwc3_gadget_suspend. Salva o estado de conexão imediatamente antes da operação. Uma desconexão que retorna erro também provoca tentativa de reconexão, pois o driver pode ter alterado softconnect/hardware parcialmente. Um gadget originalmente desconectado permanece desconectado.

Mantém referências ao dispositivo, gadget e módulo do driver, e verifica a associação do driver sob device_lock antes de cada acesso. Se houve unbind, retorna -ENODEV sem acessar o drvdata salvo.

## Watchdog Gunyah

Usa callbacks tipados de qcom_wdt_ops do cabeçalho do kernel, com retorno verificado. Remove MMIO e qcom_wdt_disable_set via kallsyms. O estado de pet/timers é suspenso e restaurado explicitamente: os helpers PM deste kernel ignoram erros dos callbacks, por isso não são usados.

Aceita o driver gh-watchdog com configuração ativa e tarefa inicializada; estados desativados/panic-only são recusados. Congela o reagendamento, sincroniza os timers, verifica reset/disable/enable e atualiza last_pet após reset bem-sucedido. A restauração rearma timers com um novo intervalo, como na retomada normal do driver; não tenta recuperar um prazo já expirado.

preserve_watchdog mantém o watchdog armado durante a preparação. Com watchdog_recovery, permanece armado para recuperação; sem recovery, é desativado antes da fronteira irreversível. Timeouts não são modificados. watchdog_control é recusado com -EOPNOTSUPP porque não existe operação para ler/restaurar o bite timeout original. disconnect_qmp também é recusado por não ter protocolo de rollback validado.

## Erros e restauração

Até kernel_restart_prepare, falhas retornam pela limpeza comum: watchdog, USB, syncboss, GPU, usuários e lock de suspensão. O primeiro erro é preservado; cada erro adicional de restauração é registrado. Falha de restauração após operação bem-sucedida também retorna erro. A limpeza libera referências mesmo se a restauração falhar.

Uma falha de disable pode ter alterado o watchdog: nesse caso a restauração força uma tentativa de enable pelo driver. Se o hypervisor rejeitar enable, o estado real fica incerto, isso é registrado e retornado como erro. O estado de software é retomado para permitir tentativas de pet, sem afirmar que o hardware foi restaurado.

A desativação do watchdog seguro via SCM ocorre por último, antes do desligamento irreversível. secure_watchdog_control=2 com execute é adiado até essa etapa. Essa API não tem operação inversa; uma falha restaura USB/watchdog de aplicação, mas não permite garantir restauração do watchdog seguro. Após kernel_restart_prepare não existe retorno recuperável neste fluxo.

## CFI e validação

Execução/preflight, test_cpus, warm_reset_test e usb_log permanecem bloqueados sob CFI devido aos demais símbolos privados. Os novos helpers estão integrados ao fluxo de execução no fonte, mas LTO elimina esse caminho bloqueado do módulo CFI final. O objeto separado de auditoria ARM64 valida os helpers, seus símbolos exportados e instrumentação; não representa autorização nem teste de execução no aparelho.

Compilação sem erros/avisos novos. Verificações de CRC, BTF, configuração e CFI/SCS passaram. Testes host exercitam o código de produção com APIs simuladas: falhas parciais, ordem inversa de restauração, erro primário, erro de cleanup, driver removido, referências/locks e modos não suportados. ASan/UBSan ativos; LeakSanitizer desativado pela limitação de ptrace do ambiente. Os testes não simulam concorrência real do kernel, firmware ou MMIO. Nenhum módulo foi carregado no Quest 3.

## Aplicação

Na raiz do quest-kexec, aplique apenas um patch: from-scm-dt.patch sobre o pacote anterior SCM/DT, ou from-original.patch sobre os fontes originais enviados. Ambos foram verificados com git apply --check. module contém os fontes e os três módulos. Scripts de build/auditoria mantêm os caminhos de /workspace/quest3-build; toolchain e kernel não estão incluídos. Não habilite execução removendo o bloqueio de CFI: os demais caminhos privados continuam pendentes.
