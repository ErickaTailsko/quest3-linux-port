# Operação e continuidade

## Estado em que o trabalho foi deixado

Root recuperado pelo Singularity na quinta tentativa; o app causou reinícios
completos durante as anteriores. A última captura RO passou e foi descarregada.
O último ciclo reversível de política reset confirmou restauração COLD e
limpeza de ambos os módulos. O pedido WARM seguinte atravessou outros boots;
o módulo de guard não é instalado automaticamente no boot novo.

Não foi adicionado um serviço de boot para quest-kexec. O início automático
descrito pelo usuário pertence ao Singularity/root. O bootloader continua
travado. Não foram prescritos flashes de partições ou uma instalação SteamOS.

## Antes de retomar

1. Ler STATUS e LOG-RETENTION e preservar os dados dos testes anteriores.
2. Manter Android/ADB/root estáveis; não repetir o ciclo de resets para apenas
   obter outra captura tardia com a mesma ambiguidade.
3. Estabelecer captura antes do root instável ou um canal independente.
4. Só depois revisar um experimento que produza evidência nova e registre
   procedência de cada boot e qualquer recuperação física utilizada.

A falha de root após um teste não deve ser atribuída automaticamente ao WARM,
nem descartada como irrelevante. Quando o problema apareceu, os testes foram
suspensos; foi sugerido force-stop do aplicativo via ADB enquanto se avaliava
estabilidade. O usuário esclareceu em seguida a recuperação do root.

## Transporte ADB

Para a próxima coleta de mapas de memória, usar o
[coletor RO dedicado](reports/2026-11-17-memory-map-collector.md) somente com
ADB/root já estáveis. Ele não carrega módulos, faz leituras com boot antes/depois
e mantém os brutos em `private-diagnostics/` por padrão. A primeira coleta
no aparelho passou; [resultado](reports/2026-11-17-memory-map-device-result.md).
Timeout/falha preserva evidência rejeitada, sem retry ou reset.

EOF/no devices ocorreu em push e pull. Não interpretar um anúncio de arquivo
enviado ou exit0 sem bytes como transferência íntegra. Os uploaders usam
arquivo temporário e offsets idempotentes; verificam SHA256 antes do nome
final. O coletor lê sysfs em registros4KiB para evitar short reads.

Uma resposta perdida após insmod não prova que a inserção falhou. Os
controladores marcam possibilidade de posse e tentam cleanup. Uma resposta
perdida após o pedido de reboot também não prova cancelamento: o controlador
não repete o reset nem restaura a política durante shutdown potencialmente
em andamento. Isso deve ser avaliado pelos relatórios e pelo boot ID.

## Preservar evidência

Não regravar um marcador apenas porque sua resposta falhou. O teste PMSG
consome cerca64KiB do ring diagnóstico; preserva-se a captura anterior e
confirma-se o marcador em uma referência real antes de qualquer reset.
Não sobrescrever diretórios before/after. Os scripts recusam destinos já
existentes e reportam capturas incompletas em vez de validá-las.

Registre sempre IDs de boot, hashes, estado guard, retorno ADB, insmod/rmmod
e todos os resets intermediários. Boot reason sozinho não demonstra DRAM
retida ou a rota de firmware. Um boot ID diferente confirma mudança de kernel,
não o número de resets entre as duas observações.
