# Marcador PMSG no mesmo boot — 2026-11-16

**Resultado: aprovado no escopo de emissão/captura no mesmo boot.**
Teste autorizado pelo usuário, sem reset, alteração de console, instalação de
hook, handoff ou flash. Não valida retenção WARM ou escrita de callbacks finais.

## Procedimento realizado

1. Confirmados ADB/root, kernel esperado, dispositivo `/dev/pmsg0`, ausência
   do módulo snapshot e DT atual íntegro. Preservada a captura anterior.
2. Executado `stage-pmsg-test.py` uma única vez, com dispositivo selecionado
   por `ANDROID_SERIAL`. Payload temporário com hash conferido antes da escrita.
3. Escrita única em PMSG: retorno zero, sem resposta incerta nem repetição.
4. Módulo RO com hash/ABI conferidos enviado em caminho temporário único;
   inserção, coleta de 36 blocos, verificação de hash e remoção confirmadas.
5. `check-pmsg-baseline.py` aprovou a captura contra metadados da escrita e DT.
6. Confirmados boot ID consistente, interface snapshot ausente e temporários
   removidos. Nenhum reset foi solicitado.

## Resultados

| Medida | Valor |
|---|---|
| Payload escrito | 65.586 bytes, incluindo 65.536 bytes de preenchimento |
| SHA-256 do payload | `e810c7594a3179f41934fbe06c467412aaa6f43647000dc11f8367d98a42d0e3` |
| Snapshot | 589.824 bytes |
| SHA-256 do snapshot | `b370dd0c3dfc2888fef4936f8bd9898222eedd9e09b20cf365ebd9b33f959bb5` |
| PMSG físico, conforme DT | `0xbfa70000` |
| Offset do marcador no payload PMSG | 66.248 |
| Ocorrências do marcador | 1, presente no ring lógico |
| Cabeçalho PMSG | start=66.298, size=66.298, válido |
| Baseline verificado | sim |
| Mesmo boot entre escrita e coleta | sim |
| Remoção do módulo e temporários | confirmada |

O preenchimento consumiu parte do ring diagnóstico conforme previsto. O
marcador permanece em PMSG: não foi apagado para desfazer o teste. Nenhuma
conclusão sobre bytes anteriores deve ignorar essa escrita deliberada.

## Evidência e privacidade

Arquivos completos em `private-diagnostics/pmsg-same-boot-01/`, ignorados pelo
Git: preflight, DT, `marker/test.json`, `baseline.json`, `experiment.json`,
snapshot, registros de operação e verificação final. Este resumo omite serial,
boot ID completo, token do marcador e logs privados.

O campo `marker_written=false` no registro do controlador de snapshot descreve
apenas esse controlador; a escrita anterior está em `marker/test.json`.
`experiment.json` registra o resultado combinado para evitar ambiguidade.

## Limites e próximo bloqueio

Foi demonstrado o caminho PMSG → snapshot → transferência → verificador no
boot corrente. Não houve boot posterior, comparação entre resets ou teste de
callbacks finais. O snapshot da memória viva não é atomicamente congelado.

Não repetir WARM/root/coleta tardia: antes é preciso garantir captura anterior
a todos os consumidores do pstore ou validar transporte independente. A janela
root/panicreporter observada nesta sessão é uma hipótese a investigar, não uma
solução early-root comprovada. Não há autorização implícita para novo reset.
