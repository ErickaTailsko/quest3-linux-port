# Publicação de cache e fronteiras do fluxo — revisão offline

**Revisão estática concluída; nenhuma rota de publicação/entrada aprovada.**
Permanecem 65 grupos host, sem novo grupo de testes. Não foram criados helpers,
adaptadores, mappings ou writers; loader/assembly e artefatos permanecem intactos.
Não houve build kernel/Android nem operação no Quest.

## Escopo e fonte

Continuação do [confronto de ABI](2026-11-18-direct-staging-stock-abi-review.md).
Fontes locais `.work/kernel`, revisão
`dbc2bc83a2b673f5d1c24ee9dadb0cd708ffda3f`, preparação
`.work/cma-identity-stock-out/`, e `quest3/module/`. Hashes e snapshots em
`private-diagnostics/cache-publication-boundary-review-01/`.

O fluxo `qkx_execute` abaixo é **código de referência bloqueado**, não execução
histórica: `qkx_resolve`, `loader.c:207-215`, recusa os caminhos privados sob CFI;
`loader.c:926-931,1026-1031` também condiciona execute ao build experimental.
Não alterar esses gates nem tomar a análise de código como permissão de ativação.

## 1. Alternativas de publicação

| Alternativa | O que existe | Resultado desta revisão |
|---|---|---|
| Importar helper stock de PoC | Implementações internas de `__flush_dcache_area`/`__clean_dcache_area_poc` | Ausentes da tabela de exports fornecida; não resolver endereço privado |
| Usar helper local leaf de cache | `qkx_flush_dcache_area` existente usa `dc civac`, `dsb sy` e retorno | Candidato a **estudo de prova**, não substituto aprovado; precisa de contrato próprio de ranges/contexto/CPU/CFI |
| Integrar em caminho kernel suportado | Fonte `machine_kexec` publica listas, código e segmentos já colocados | Referência de protocolo, não rota stock disponível; KEXEC/KEXEC_FILE desativados na config preparada |
| Usar `flush_dcache_page` ou só I-cache | Exports disponíveis | Não satisfaz o contrato geral PoC dos destinos; não adotar |
| Chamar DMA API com device real/fictício | APIs têm semântica de ownership e coerência de dispositivo | Não é substituição genérica de publicação para entrada CPU; nenhum device/contrato apropriado foi estabelecido |
| Mapear uncached, autocopiar ou ler de volta | Conversões/mappings e leituras são mecanismos distintos | Não prova PoC; pode criar aliases incompatíveis ou destruir dados dirty; não adotar como atalho |

Não se escolheu uma implementação. Para preservar stock e não depender de
símbolos privados, a investigação seguinte mais limitada seria **especificar
as obrigações de um helper local**, sem escrever assembly ou incluí-lo no loader.
Isso não resolve shutdown, entrada CFI, posse ou lifetime.

### Diferenças concretas que a prova local teria de cobrir

`arch/arm64/include/asm/assembler.h:315-329,395-430` distingue
`raw_dcache_line_size` (CTR da CPU atual) de `dcache_line_size` (valor seguro
entre CPUs via `read_ctr`/alternativas). O helper local em
`quest3/module/transition.S:189-203` usa a variante raw; o helper stock usa o
macro de valor seguro. Não assumir equivalência em CPUs heterogêneas, migração
ou cache types divergentes. Uma CPU online ao fim não prova todo o histórico
de writes/aliases nem substitui essa revisão.

Stock `cache.S:99-111,171-192` separa clean+invalidate (`civac`) e clean (`cvac`)
até PoC. O macro aplica alternativas/errata para certas operações. A config
preparada habilita `CONFIG_ARM64_WORKAROUND_CLEAN_CACHE`, mas configuração não
demonstra quais capabilities/patches se aplicam em runtime. O fato de o helper
local já usar `civac` não prova cobertura de todos os requisitos da plataforma.

`arch/arm64/kernel/module.c`, `module_finalize`, trata `.altinstructions` de
módulos. Isso não torna qualquer cópia de bytes de código equivalente ao texto
patchado original: relocação, referências externas, patching e endereço de
execução precisam de revisão separada. Nenhuma cópia nova foi preparada.

Uma especificação local ainda precisaria cobrir:

- Tipos de argumentos/entrada CFI e ABI de chamada/retorno, SCS/x18 e registradores
  preservados; sem `__nocfi`, casts privados ou relaxamento das proteções.
- VA válida, mapping Normal/atributos coerentes, lifetime do mapping durante a
  chamada e contexto de CPU/IRQs/preempção explicitamente definido.
- Ranges de destino realmente escritos, código e tabelas finais; alinhamento de
  linhas, zero length, overflow e bordas dentro de recursos próprios. Não usar
  somente a lista legada `owned[]` para alegar cobertura dos destinos novos.
- Última escrita anterior à manutenção, ausência de writes posteriores e
  exclusão contínua de writers/DMA. Clean não é trava nem revogação de DMA.
- Operação/barreira adequada e revisão dos errata aplicáveis; publicação de
  código/I-cache e protocolo MMU/entrada continuam obrigações distintas.

### PoC e I-cache não são intercambiáveis

`asm/cacheflush.h:74-96` mostra que `flush_icache_range` inline pode enviar IPIs.
O fonte `arch/arm64/kernel/machine_kexec.c:170-188` usa a variante `__*` e explica
o risco de IPIs após parar CPUs, além de limpar explicitamente segmentos já
colocados. Essa é evidência da **separação de obrigações**, não prova de que o
loader customizado possa chamar esse caminho. Não há `struct kimage` adquirida
nem backend stock KEXEC habilitado por esta revisão.

## 2. Não existe uma única fronteira "antes do salto"

A tabela localiza efeitos no **fonte atual**, não certifica reversibilidade
hardware nem que o primeiro efeito irreversível real esteja completamente
enumerado. Callbacks podem ter efeitos parciais antes de retornar erro.

| Ordem / localização em `loader.c` | Efeito | Limite relevante |
|---|---|---|
| 697-702 | Preflight-only pode retornar antes de freezer | Não é prova de segurança dos passos seguintes |
| 703-737 | Lock system-sleep, flags de wakeup, kthread e `freeze_users()` | Observador/supervisor userspace pode congelar; checkpoint/ACK dependente dele precisa anteceder o freezer |
| 738-750 | Suspend GPU e syncboss opcional | Há tentativas de resume no abort; retorno/cleanup pode falhar e não prova quiescência global |
| 756-758 | `qkx_usb_disconnect()` | Pode perder transporte/observação antes de shutdown global; reconexão é tentativa, não confirmação de entrega |
| 759-764 | Prepare/finish do watchdog apps | Muda timers/callbacks/estado, restauração pode ser incerta; sem garantia de rollback total |
| 768-774 | Chamada condicional de desativação do watchdog seguro | API sem inversa conhecida: boundary conservador **antes da tentativa**, não só após sucesso |
| 777-780 | `kexec_in_progress`, checkpoint 11, `kernel_restart_prepare(NULL)` | Reboot notifiers, SYSTEM_RESTART, disable usermodehelpers e shutdown de devices; não há abort global pareado |
| 782-794 | Migração, hotplug e `machine_shutdown()` | Shutdown de CPUs não é simples pin loop e não oferece retorno ao estado original |
| 795-828 | RPMh e probe opcionais | Podem falhar após shutdown; probe restaura código com memset/memcpy, criando writes tardios |
| 829-841 | Sleep, IRQ/preempção off, flush de `owned[]`, I-cache e trampoline | Já após efeitos irreversíveis; checkpoint/sleep não é recibo nem prova de observação USB |

O ramo seguro no corpo de execute depende de `!preserve_watchdog ||
secure_watchdog_control == 2`. Os guards de modos no init restringem combinações;
não inferir que todo modo listado no corpo seja alcançável com execute. Mesmo
que o ramo de watchdog seguro seja pulado, `kernel_restart_prepare` continua
sem contrato de rollback. Isso não transforma os passos anteriores em região
globalmente reversível certificada.

### O que os caminhos de erro realmente demonstram

`quest3-scm.c:176-196` chama `qcom_scm_sec_wdog_deactivate()` no modo 2, sem
operação inversa. No execute, erro nessa chamada vai a `release_devices`.
Esse label chama abort de USB/apps-watchdog, resume de syncboss/GPU, thaw e
restaura flags/locks; **não restaura watchdog seguro**. Portanto, não classificar
esse goto como rollback completo nem usar o comentário "last fallible step"
como prova de ausência de efeito persistente. Resultado incerto continua incerto.

`quest3-platform.c:147-180,267-294,362-376` registra erros de restauração, mas
também solta referências/zera estruturas locais. Não transplantar esse cleanup
legado para o contrato novo de retenção em incerteza. Nesta revisão ele não foi
executado nem modificado; a discrepância fica como requisito de redesign antes
de qualquer port operacional.

`kernel/reboot.c:74-80` faz chamadas de preparação sem retornar status de
quiescência por dispositivo. `drivers/base/core.c:4358-4425` chama shutdown_pre,
bus/driver shutdown e altera a lista de devices. Retornar de `prepare(NULL)`
não comprova que todos os engines DMA/SMMU estejam quietos. `process.c:124-127`
encaminha machine_shutdown para shutdown de CPUs, não para auditoria de DMA.

## 3. Consequências para staging direto e para o modelo host

O trace host atual tem um único evento `irreversible-boundary`. Ele verifica
ordem abstrata e não foi alterado: **não corresponde automaticamente à PHASE 11**.
Em eventual refinamento, é preciso separar pelo menos:

1. Última confirmação possível do observador, antes de freezer/perda de transporte.
2. Última oportunidade de abort sob um contrato de restauração realmente revisado.
3. Tentativa de efeito sem inversa/efeito desconhecido: sem retry/cleanup automático.
4. Shutdown global/CPU e manutenção final: sem I/O normal ou rollback ordinário.

Staging, zero-fill, validação e selagem precisam terminar enquanto seus serviços
estiverem disponíveis, antes de freezer/shutdown que os inviabilize. Publicação
antecipada pode ser hipótese de design se não houver writes posteriores, mas
não é prova de estabilidade até entrada. O probe opcional atual reescreve código
depois do shutdown, logo um clean feito apenas antes dele não cobre a versão
final desse código. A manutenção final atual ocorre depois dessa reescrita;
não mover nem reutilizar esse ponto sem revisar todos os recursos.

Não exigir ACK normal de um supervisor congelado ou de USB desconectada. A
captura recuperável de logs finais requer mecanismo independente revisado;
nenhum sleep, printk, receipt anterior ou leitura histórica fecha esse gate.
Monitor/âncora continuam bloqueados. Timeout/interrupção/falha de journal
congela comandos posteriores, inclusive reads/cleanup automáticos.

## Resultado e próximo gate

**Nenhum helper ou caminho sem cópia aprovado.** A lacuna de publicação não
se resolve trocando nomes de função, e o fluxo legado não oferece uma fronteira
única de rollback seguro. Posse, lifetime, mappings, cache e DMA não foram
validados no alvo; a Image ainda exige 32 MiB CMA na hipótese atual.

Próximo passo possível, ainda offline: especificar a cobertura por ranges e
última escrita de um eventual helper local, separando publicação de payload,
código e tabelas e as fronteiras de observação/irreversibilidade. Não implementar
assembly, writer, adaptador ou handoff por consequência desta revisão. Qualquer
operação no aparelho exige nova autorização específica; CFI/SCS/Full LTO/
MODVERSIONS e os gates operacionais existentes permanecem intactos.
