# Ensaio CPU separado — experimental, não kexec
Compilado com q3make contra o kernel stock preparado, CFI/SCS/Full LTO.
Sem alterar o quest_kexec que passou no preflight do aparelho.
Padrão target_cpu=-1 apenas registra contagens. Parâmetro positivo retira e
restaura UMA CPU, nunca CPU0, sem trampoline/MMU/SCM ou shutdown de drivers.

Testes host executam a função C real com APIs simuladas: sucesso, CPU0,
afinidade, retirada recusada, CPU já offline, restauração recusada, corrida
na máscara e preservação do primeiro erro. Não validam o hardware.

Limitações: APIs públicas serializam cada operação, não toda a sequência;
Android/firmware podem fazer hotplug simultâneo. Leitura de máscaras detecta
algumas mudanças, não todas as corridas ABA. Não é base suficiente para um
shutdown kexec. Falha de add_cpu pode deixar a CPU offline; é reportada e a
afinidade é restaurada quando possível, não há promessa de rollback infalível.
Não foram realizados testes no aparelho. Não instalar automaticamente.

## Evidência enviada pelo usuário: CPU1
Log quest3-cpu1-test-log.txt: em 254.667832 PSCI confirma CPU1 killed;
em 254.675538 CPU1 volta; em 254.678004 restore=0 e 254.678012
affinity_restore=0 result=0. Usuário confirmou insmod/rmmod=0 e online=0-5.
Nenhuma falha CFI/Oops/panic observada nesse trecho. AVC perf_event em
permissive=1 não bloqueou a operação.
O log ampliado também registra SIGSEGV de app_process64 em 153.830324,
~183 ms após a inspeção anterior (153.646862), muito antes do hotplug CPU1.
Causalidade não determinada; não afirmar ausência de falhas após inspeção.
Ainda não valida todas as CPUs, exclusão de hotplug concorrente, DMA ou kexec.
