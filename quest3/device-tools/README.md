# Coleta somente de leitura

Execute no computador que tem ADB e o Quest autorizado:

```sh
python3 collect-readonly.py --serial SERIAL_DO_QUEST --out quest3-diagnostics
```

Se o aparelho já tiver `su` e as leituras exigirem root, acrescente `--root`. Isso usa o `su` existente apenas nas leituras; não roda `adb root`, não instala ferramentas e não carrega módulos. Sem `--serial`, exige exatamente um dispositivo autorizado. O diretório de saída deve ser novo.

O coletor salva versão/configuração do kernel, DT disponível e propriedades core-hang em hexadecimal, vínculos GPU/USB/watchdog/syncboss, estado software do watchdog, dmesg e listagem de pstore. Alguns arquivos podem ser inacessíveis em determinados firmwares: cada retorno/erro fica no manifest.json e em arquivos .stderr; as outras leituras continuam. Saída 0 indica todas as leituras concluídas; 2 indica coleta parcial ou seleção inválida.

Uma coleta parcial não confirma ausência de recurso no firmware. Configuração com PSTORE não confirma, sozinha, que o conteúdo persistirá após a falha. Este script não captura continuamente logs durante o desligamento nem substitui o transporte EP0 que permanece bloqueado.
