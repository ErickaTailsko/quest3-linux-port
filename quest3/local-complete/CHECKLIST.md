# Checklist detalhado — quest-kexec / Quest 3

Legenda: **concluído localmente** = fonte/compilação/testes indicados passaram; **pendente no aparelho** = não executado; **bloqueado por interface** = falta uma API adequada, um protocolo de restauração ou uma integração ao kernel alvo. Um teste simulado não confirma funcionamento físico.

## 1. Itens concluídos neste ambiente

| Item | Trabalho realizado | Evidência e limite |
|---|---|---|
| Kernel de referência e toolchain | Reproduzidos kernel 5.10.246-gd7102a837402 e módulos com Clang 14.0.7 | CRCs, configuração, BTF e artefatos verificados; commit interno do aparelho não foi confirmado |
| CFI/SCS/LTO | Mantidos CFI estrito, Shadow Call Stack e Full LTO | Flags de compilação e símbolos dos binários; não foi removida proteção para contornar erros |
| `x18` | Salvamento/restauração junto com LR no frame de 96 bytes | Modelo de pilha sobre desassembly: 100 padrões, original falha em x18, corrigido passa; não executa MMU/EL1 |
| SCM | Substituído ABI legado pelas funções `qcom_scm_*` exportadas | Compilação, CRCs e testes com falhas simuladas |
| Device Tree | Core-hang usa `qcom,chd-percpu-info`, sem fallback para endereços fixos | Valida cobertura dos CPUs, alinhamento, duplicatas e formato antes do acesso; DT real ainda precisa ser coletado |
| Ordem das alterações SCM | Imagens/staging e leituras são validados antes da alteração persistente | Falha de staging não chama SCM; uma alteração por carga; duas alterações ou combinação com testes/execução são recusadas |
| Erros SCM | Retorno de firmware propagado; core-hang tenta restaurar após falha interna | Falha de restauração registrada; watchdog seguro não tem operação inversa disponível |
| USB | APIs gadget do driver, tratamento de runtime PM pelo DWC3 e reconexão após falha parcial | Testes de conexão original, falhas, desvinculação e referências; controlador real não acionado |
| Watchdog de aplicação | Callbacks Gunyah tipados; erros verificados; timers retomados no rollback | Testes de reset/disable/enable e falhas de recuperação; estado físico pode permanecer incerto se o hypervisor rejeitar restauração |
| GPU | Callbacks `dev_pm_ops` do KGSL, referências e proteção contra desvinculação | Suspend/resume, falhas parciais e cleanup testados com mocks; não houve suspensão real |
| APIs exportadas | Afinidade, hotplug, locks de suspensão e RPMh agora têm chamadas diretas | Cinco referências ao resolvedor removidas; protótipos oficiais |
| Erros em testes de CPU/RPMh | Resultado de CPU inicializado; primeiro erro preservado; RPMh não é ignorado | Testes simulados de afinidade/online e inspeção do fluxo; CPU offline real não testado |
| Preflight independente | `preflight_only=1 execute=0` verifica GPU/USB/watchdog e prontidão SCM | Não prepara imagens nem executa callbacks; 15 combinações conflitantes são recusadas antes de acessar dispositivos |
| Auditoria privada | Inventário atualizado das 18 referências restantes | Inclui código QMP desativado; nenhuma está exportada no kernel reproduzido |
| Regressões | Executor único `run-local-checks.py` e relatórios | Dez verificações, incluindo modelos de registradores, falhas e inspeção dos artefatos |
| Diagnóstico para o aparelho | `device-tools/collect-readonly.py` preparado | Testado com ADB simulado: seleção de dispositivo, root opcional, leituras com erro e proteção contra sobrescrita; não carrega módulos |

Alteração de comportamento SCM: `core_hang_control=1/2` e `secure_watchdog_control=1/2` no fluxo normal agora dependem de staging bem-sucedido. O preflight continua sem precisar de Image/initrd/DTB. Uma alteração SCM bem-sucedida é persistente; não é desfeita ao descarregar o módulo. O modo de consulta SCM informa prontidão do driver, não suporte do firmware a cada comando.

## 2. Alternativa nativa que pode ser preparada aqui

- [x] Confirmar no Kconfig que ARM64 oferece kexec nativo.
- [x] Confirmar que o kernel reproduzido tem KEXEC e KEXEC_FILE desativados.
- [x] Criar configuração isolada com KEXEC/KEXEC_CORE/CRASH_CORE, preservando CFI/SCS/LTO e demais opções.
- [x] Compilar os componentes `machine_kexec`, `relocate_kernel`, `kexec` e `kexec_core`.
- [x] Compilar e verificar o kernel experimental completo e seus 272 módulos — kernel nativo ligado, BTF/CRC/CFI verificados; não testado no aparelho.
- [ ] Montar imagem de boot compatível com o Quest — depende de dados reais de boot/vendor_boot, DTB/DTBO, módulos e recuperação.
- [ ] Inicializar o kernel experimental no aparelho — não pode ser validado apenas neste ambiente.

A versão experimental é distinta: `5.10.246-gd7102a837402-qkx-native-probe`. Ela não substitui o kernel de referência e não libera o salto do módulo stock. Há 12 CRCs exportados diferentes da compilação stock; os módulos dos dois conjuntos não devem ser misturados. Consulte `native-kexec-plan.md`.

## 3. Pendências técnicas que permanecem bloqueadas

| Pendência | O que pode ser feito aqui | O que falta para concluir |
|---|---|---|
| Freezer/desligamento/CPUs no módulo atual | Auditar chamadas, manter bloqueios, estudar integração nativa | Não há API exportada suficiente; precisa integração ao kernel alvo ou alternativa validada |
| Execução e ensaios 2/3 sob CFI | Testar as recusas e compilar o caminho alternativo | Resolver dependências anteriores e validar plataforma; NÃO retirar o guard de CFI |
| Warm reset | Examinar caminho de reboot | `force_warm_reboot` e caminho privado impedem garantir o reset desejado; reboot comum não é substituto equivalente |
| Log USB EP0 (`usb_log`) | Auditar UDC e preparar coleta via ADB/pstore | Não existe hook exportado validado para interceptar o gadget Android existente com segurança; permanece bloqueado |
| QMP/AOP | Analisar protocolo e DT | Falta fechamento/reconexão validado; `disconnect_qmp` permanece recusado |
| Calibração de watchdog | Analisar callbacks e timeouts | Não existe getter do bite timeout para restauração exata; `watchdog_control` permanece recusado |
| Syncboss | Inspecionar DTS e coletar vínculo real do driver | A árvore fornecida tem DTS, mas não foi encontrado fonte do driver correspondente; contrato suspend/resume ainda não validado |
| Concorrência | Exercitar falhas em mocks e revisar locks/referências | IRQs, runtime PM, unbind, DMA e callbacks concorrentes precisam do driver/kernel reais |

## 4. Ordem dos testes no aparelho

1. **Coleta somente de leitura:** executar o coletor e conferir `/proc/version`, configuração, Device Tree, vínculos dos drivers e logs. ADB com root foi confirmado pelo usuário no computador conectado ao Quest (`uid=0`, contexto Magisk). Não há conexão ADB neste ambiente; nenhuma coleta real foi realizada aqui. O método de boot/recuperação ainda não foi confirmado.
2. **Compatibilidade:** confirmar release, configuração de segurança e símbolos/módulos do firmware em execução. Vermagic igual, isoladamente, não prova compatibilidade.
3. **Recuperação e logs:** confirmar um caminho real de recuperação e captura após falha. pstore está habilitado na configuração, mas sua disponibilidade após reboot ainda precisa ser verificada.
4. **Carga/preflight:** carregar o módulo compatível apenas com `preflight_only=1`, observar retorno/dmesg e descarregar. Conferir que não há falha de CRC, CFI ou SCS.
5. **Staging:** validar os arquivos de destino e a janela de RAM, carregar com `execute=0`, observar a preparação e descarregar. Nenhum salto deve ocorrer nessa etapa.
6. **DT/SCM:** conferir endereços e aceitação de leituras. Testes de escrita exigem etapa separada; o watchdog seguro não tem rollback garantido.
7. **Drivers:** testar suspensão/retomada e erros de USB/GPU/watchdog com um caminho de execução validado. O pacote atual ainda bloqueia os ensaios dependentes de símbolos privados.
8. **Transição física:** testar o roundtrip e a cópia scratch, com recuperação/logs disponíveis. O teste local de x18 não substitui essa etapa.
9. **Kernel alternativo:** conferir formato de boot, módulos externos, firmware e requisitos de assinatura antes de montar/inicializar a versão nativa experimental.
10. **Salto e boot do destino:** somente depois das etapas anteriores; verificar CPUs, memória, caches/MMU, DMA, USB, GPU, watchdog, sensores e logs iniciais do destino.

Nenhuma carga, escrita de partição, publicação, reboot, alteração do bootloader ou execução kexec foi feita nesta sessão. Os artefatos e scripts locais estão prontos para revisão; os itens do aparelho continuam pendentes, não marcados como concluídos.
