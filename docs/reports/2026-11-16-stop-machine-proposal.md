# Alternativa experimental de amostra pageblock

**Atualização posterior:** uma execução foi autorizada, realizada e removida;
veja o [resultado](2026-11-16-pageblock-device-result.md). Os estados de não
execução abaixo descrevem a fase de preparação e foram preservados como histórico.

**Limite para ampliação:** a revisão de 2026-11-17 identificou caminho vendor
de remoção de subseções que também precisa entrar na prova de lifetime. Não
generalizar o escopo das 13 cabeças ou tomar locks dentro do callback por
suposição. [Análise atual](2026-11-17-memory-lifetime-review.md).

## Avanço

Preparado e compilado `q3_pageblock_snapshot`, separado do protótipo de varredura
que continua recusando hotplug. O novo módulo fica desarmado por padrão e usa
stop_machine com callback tipado para amostrar apenas 13 cabeçalhos de blocos.
**Não foi enviado ou carregado no Quest. Não houve nova operação ADB nesta etapa.**

A revisão de stop_machine.c mostra barreiras de entrada em RUN depois de IRQs
desabilitadas nos participantes. O callback selecionado pode observar metadados
sem que tarefas de hot-remove em outros CPUs avancem durante essa janela.
A leitura usa pfn_to_online_page, não somente pfn_valid. É uma proposta de
contrato baseada na fonte pública, não validação do binário/firmware real.

## Risco distinto da leitura anterior

O módulo não escreve na região nem migra páginas, mas parar os CPUs altera a
execução do sistema e pode causar latência, watchdog ou travamento. Por isso
não foi classificado como diagnóstico operacionalmente passivo e não foi
executado apenas com a autorização anterior de coleta ramoops/PMSG.

O callback tem orçamento de 1 ms, conferido entre amostras e ao final. Não é
limite rígido da pausa global: rendezvous, CPUs travados e firmware não estão
cobertos. Nenhuma alocação, espera, formatação ou printk ocorre no callback.

## Compilação e auditoria

- Fonte pública fixada, toolchain Android 14.0.7 e patch OpenSSL host documentado.
- Config stock fornecida usada sem mudança por olddefconfig.
- modules_prepare para headers/ferramentas; CRCs vêm explicitamente da tabela
  stock fornecida, não de uma suposta produção de CRCs por modules_prepare.
- Compilação externa com CFI, SCS, Full LTO e reserva de x18.
- Vermagic: `5.10.246-gd7102a837402 SMP preempt mod_unload modversions aarch64`.
- 21 imports versionados conferem com a tabela fornecida; sem imports de
  alocação contígua, migração, resolução privada ou reinício.
- SHA-256 módulo: `ee4692aada2c6b6b5fc562f84b2c1d9210d5b0fdb69aa83577c47b6a9cddbbc5`.

Metadados públicos: `quest3/pageblock-stop-snapshot/build-verification.json`.
Binário e logs privados preservados no projeto. Não se demonstrou equivalência
completa da fonte/estruturas ao binário do fabricante ou segurança runtime.

## Testes e interpretação

Testes compilam o callback real com mocks e verificam IRQ, amostras fixas,
recusas offline/device, falha parcial e orçamento. Suíte: **30 aprovações**.
Não simulam barreiras reais do stop_machine, IRQs, firmware ou watchdogs.

A amostra retorna migratetype numérico do header usado no build. Com CMA e
isolamento habilitados nessa árvore: 0=UNMOVABLE, 1=MOVABLE, 2=RECLAIMABLE,
3=CMA, 4=HIGHATOMIC, 5=ISOLATE. Não usar enum de outra revisão por suposição.

Mesmo 13 cabeçalhos MOVABLE não comprovam validade/reservabilidade de todas as
páginas, não isolam memória e não resolvem DMA/SMMU. A sonda não fecha o gate
de posse da janela. O protótipo anterior permanece bloqueado e preservado.

## Próxima decisão

Revisar/autorizar explicitamente uma única carga com pausa global, captura e
remoção, sem reset ou aquisição de memória. Até lá, nenhum ensaio no Quest.
O protocolo de coleta e cleanup está no README do módulo.
