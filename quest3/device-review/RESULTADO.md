# Análise dos quatro arquivos do Quest

Release confirmado: 5.10.246-gd7102a837402. Compiler informado pelo aparelho: Android clang r450784e 14.0.7, LLD 14.0.7. Correspondem aos utilizados para os módulos stock.

A configuração recebida é semanticamente idêntica ao device.config anterior. CFI estrito, CFI shadow, Shadow Call Stack, Full LTO e MODVERSIONS estão ativos. MODULE_SIG, KEXEC e KEXEC_FILE estão desativados. PSTORE e PSTORE_RAM estão ativos.

Comparando com out/.config, as opções compartilhadas diferem apenas em LOCALVERSION_AUTO (aparelho y, build n, com release fixado explicitamente) e PAHOLE_VERSION (0 versus 132). Há também 70 opções marcadas como desativadas no aparelho e ausentes na árvore usada. Isso não prova identidade do fonte interno nem compatibilidade de todos os layouts privados. Os CRCs efetivos dos imports ainda devem ser confirmados pelo carregamento no kernel em execução.

O trecho de log contém 3192 linhas. Não há registros de quest_kexec/qkx, falha explícita de CFI, version magic incompatível, Unknown symbol, Oops ou kernel panic. A ausência no trecho não prova que o módulo carregou nem que nunca houve falha fora da janela capturada.

Há ciclos de suspensão/retomada de syncboss_spi spi0.0, filas miscfifo cheias, rejeições de modos do display e abortos de suspensão por fontes de wakeup, incluindo qcom_rx_wakelock. Não há evidência que os atribua ao quest-kexec.

Os quatro arquivos não incluem o Device Tree completo, os vínculos dos drivers nem a lista de módulos carregados. Esses dados faltam antes de concluir a validação da plataforma. Nenhum comando de carga/execução foi enviado ao aparelho por este ambiente.

Os arquivos de diagnóstico recebidos e este relatório não foram publicados no serviço externo. O envio externo do kernel experimental continua pendente de autorização específica; anexar diagnósticos não foi interpretado como essa autorização.
