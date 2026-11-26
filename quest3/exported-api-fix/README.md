# Chamadas diretas às APIs exportadas

Compilação: 5.10.246-gd7102a837402, Clang 14.0.7, Full LTO, CFI e Shadow Call Stack mantidos.

## Alterações

Foram removidas cinco consultas kallsyms e seus casts: set_cpus_allowed_ptr, cpu_hotplug_enable, lock_system_sleep, unlock_system_sleep e rpmh_write_sleep_and_wake. As chamadas são diretas, com protótipos dos cabeçalhos oficiais do kernel. Todas constam em Module.symvers.

O teste de CPUs inicializa o resultado mesmo quando só CPU0 está online. Falhas de restauração de CPUs, máscara online ou afinidade são registradas; o primeiro erro é preservado. Sem erro anterior, falha de restauração é retornada.

Se RPMh foi solicitado e seu dispositivo não existe, o fluxo aborta antes das alterações de hardware. Se a chamada falha após kernel_restart_prepare/machine_shutdown, ocorre panic explícito em vez de continuar o salto com erro ignorado. Nesse ponto já não há rollback recuperável. Esse ramo continua bloqueado sob CFI.

## Estado atual

O preflight independente continua disponível via `preflight_only=1 execute=0`, sem comandos de hardware nem preparação de imagens. Execução kexec, ensaios 2/3, testes de CPU, warm reset e usb_log continuam bloqueados sob CFI. Restam 20 símbolos não exportados usados pelo resolvedor; consulte remaining-private-symbols.md. Migrar as cinco APIs não libera o salto.

## Validação

Compilação sem erros/avisos novos. Verificações de CRC, BTF, configuração e CFI/SCS passaram. Testes host usam a função de teste de CPUs extraída do fonte de produção com callbacks simulados: CPU0 isolada, falhas de offline/online, falha de afinidade inicial/restauração, freeze parcial e ensaio físico com erro. Testes de rejeição de modos combinados no preflight e verificações dos bloqueios CFI passaram. Nenhum módulo foi carregado no headset; SMP, firmware, concorrência e salto não foram testados.

O patch incremental aplica sobre o pacote preflight-CFI anterior e passou por git apply --check. module contém os fontes completos e os três módulos. Não remova os bloqueios de CFI para executar os caminhos pendentes. Os testes pressupõem a estrutura /workspace/quest3-build.
