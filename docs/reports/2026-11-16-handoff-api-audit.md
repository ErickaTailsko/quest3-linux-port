# Auditoria de APIs para o primeiro handoff

## Resultado

`tools/audit-handoff-exports.py` cruzou as referências `lookup("...")` do
loader com o Module.symvers stock fornecido. **18 referências distintas,
18 ausentes dos exports.** Resultado com hashes das entradas em
`quest3/restart-backend-design/export-audit.json`.

É inventário de fonte, incluindo funções históricas/compiladas fora do módulo,
não uma afirmação de 18 imports ativos. A tabela fornecida tampouco comprova
equivalência completa ao binário interno do aparelho.

## Interfaces encontradas

Não exportadas na tabela: kernel_restart_prepare, migrate_to_reboot_cpu,
machine_shutdown, machine_restart, freeze_processes/thaw_processes,
freeze_secondary_cpus, cpu_down/cpu_up e os demais símbolos privados usados.
Também não aparecem device_shutdown, syscore_shutdown, smp_send_stop ou
kernel_kexec como APIs exportadas para um módulo.

Encontradas: kernel_restart, registros de reboot/syscore/restart callbacks,
remove_cpu/add_cpu, locks de hotplug, set_cpus_allowed_ptr, stop_machine,
alloc_contig_range/free_contig_range e request_resource. Exportação não é
garantia de contexto adequado, sucesso, rollback, tipo CFI de qualquer ponteiro
obtido por outro caminho ou segurança do protocolo de plataforma.

## Caminho de projeto possível, ainda não implementado

O desenho existente em `quest3/restart-backend-design/DESIGN.md` propõe usar
kernel_restart e callbacks oficiais para que o kernel stock execute sua própria
cadeia de shutdown. A fonte pública confirma a ordem:

```text
kernel_restart
  kernel_restart_prepare: notifier -> device_shutdown
  migrate_to_reboot_cpu
  syscore_shutdown
  machine_restart: IRQs off -> smp_send_stop -> possível EFI -> restart handlers
```

Não há um ponto genérico dessa cadeia que automaticamente satisfaça o handoff:

- notifier de reboot não cancela kernel_restart por retornar NOTIFY_BAD;
- syscore ocorre depois de device_shutdown e não preserva APIs normais de drivers;
- handler final é atômico: sem dormir, hotplug, freezer ou alocação GFP_KERNEL;
- smp_send_stop não comprova CPU_OFF PSCI nem readiness de CPUs para o kernel alvo;
- prioridades não demonstram precedência sobre todos os handlers vivos;
- remover um dispositivo/CPU antes da cadeia altera suas premissas e exige
  ensaio/rollback próprios, não simples troca de nomes de funções.

Os fatos EFI obtidos em ensaios anteriores precisam de procedência e validade
para o experimento proposto; o registro de observadores não foi autorizado
nesta etapa. Nenhum callback novo foi registrado.

## Contrato de memória: próxima unidade concreta

Antes de armar qualquer caminho irreversível, é necessário assegurar posse
da janela de destino. A exportação de alloc_contig_range é uma possibilidade
para investigação, não uma autorização para alocar/migrar 52 MiB no aparelho.

Uma reserva de recursos via request_resource, ou aprovação do iomem, não tira
páginas ocupadas do buddy allocator nem bloqueia DMA. Um projeto de posse deve:

1. Validar PFNs, memória normal, alinhamento e reservas reais da janela inteira.
2. Adquirir páginas por interface suportada, tolerando EBUSY sem relaxar limites.
3. Definir propriedade e liberação exatas em todas as falhas pré-commit.
4. Excluir fonte, descritores, código de transição e pilhas da área sobrescrita.
5. Separar posse contra alocador de quiescência DMA/SMMU; uma não prova a outra.

Não houve chamada alloc_contig_range, migração de páginas ou carga de módulo
nesta auditoria. O caminho execute continua bloqueado. Os testes de captura
PMSG no mesmo boot não satisfazem o gate de logs pós-transição.

## Limite do novo kernel QMP

O candidato QMP é o kernel ALVO. Corrigir seus drivers, habilitar funções nele
ou recompilá-lo não adiciona exports/API ao Android stock que precisa realizar
o primeiro salto. Não confundir melhorias no segundo kernel com implementação
do mecanismo de saída do primeiro.

## Verificação

```sh
python3 tools/audit-handoff-exports.py
python3 tools/run-host-checks.py
```

Novo teste sintético cobre deduplicação, exports ausentes, tabelas inválidas e
ausência de autorização implícita. Suíte atual: **27 aprovações**.
