# Captura e retenção: resultados completos

O ramoops do DT está em `0xbfa00000`, tamanho`0x90000` (589.824 bytes).
No layout analisado: dmesg`0x30000`, console`0x20000`, ftrace`0x20000`,
pmsg`0x20000`. PMSG começa em`0xbfa70000` e seu cabeçalho ocupa12 bytes.
Todos os endereços de operação são obtidos do DT; isto descreve a amostra.

## Por que o pstore vazio não conclui perda de RAM

O crash reporter possui rota de remoção de relatórios sem panic. O ramoops
também salva um old_log e zera índices no início do boot; unlink pode apagar
o registro lógico. Uma leitura tardia, após o root do Singularity, pode ocorrer
depois desses consumidores. BOOT_COMPLETED do aplicativo não garante ordem
anterior ao trigger sys.boot_completed do init.

Não foi configurado um hook early-root nem desabilitado o crash reporter.
Não se induziu panic nem se fabricou texto de panic para passar pelo filtro.
As referências a logcat -L -c foram analisadas, não executadas para limpar dados.
Os FDs oferecidos ao vendor.charger não estavam disponíveis no serviço normal;
a captura de12.803 linhas de FDs não mostrou um handle pstore recuperável.

## Snapshot bruto

`q3_ramoops_snapshot` copia apenas a região DT ramoops validada, exige driver
vinculado e formato conhecido, não aceita endereço arbitrário e não escreve
diretamente na reserva. A cópia inicial pode concorrer com escritores; depois
fica imutável em um bin_attribute root-readable. O coletor transfere blocos,
confere SHA256 e boot ID. O módulo foi inserido/coletado/removido com sucesso.

## Comparações

| Caso | Referência | Posterior | Interpretação |
|---|---|---|---|
| Console/PMSG iniciais | marcadores curtos | pstore tardio vazio | inconclusivo |
| Primeiro snapshot RO | pmsg2726 bytes | nenhum marcador anterior no raw | não distingue reset e sobrescrita anterior |
| PMSG preenchido, COLD | offset68262, size68312 | size712, cauda inteira zero | ausência confirmada, apagador não identificado |
| PMSG preenchido, pedido WARM | offset66248, size66298 | size712, cauda inteira zero | resets extras durante root impedem isolar WARM |

Hashes:

| Captura | SHA256 |
|---|---|
| Primeiro raw | `d72f71f0b58cd848bc400c1b4f02833bf13b0daed3934d28ee517e94408423f1` |
| Antes COLD | `c75b89b31e5298f6700aa4684cfc760e1a3f17932fa1e06cf378e4d68097d451` |
| Depois COLD | `7247b2501c6e6f49da4b848cac30dcc6ee767cf5f1dfb4c04f93c48b41d27d7d` |
| Antes pedido WARM | `db951b6ff6f3fc320fb40f4b0caf100b5b24a3134258092e62781066d05342ad` |
| Depois da sequência WARM/root | `c67f8514accf894ab31ea3f55752b73d72bd4dba7f2cd25bd49ac045e7475e0a` |

## O que está e não está demonstrado

O reset foi pedido com mode1/owned1 e confirmado pelo ADB. A execução do
handler/serviço de firmware WARM não foi observada. Os reinícios completos
posteriores do Singularity introduzem outra variável. Mesmo uma retenção
positiva desse marcador não provaria escrita dos callbacks finais, todos os
modos de reset ou confiabilidade universal.

Precisamos de leitura antes das tentativas adicionais de root ou transporte
independente. O observador reboot/syscore/restart já compilado não deve ser
tratado como testado em hardware. A investigação segue aberta; repetir o mesmo
fluxo de reboot/root/coleta não resolve sua ambiguidade.
