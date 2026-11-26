# Continuidade — 16 de novembro de 2026

## Escopo e publicação

Resumo revisado das verificações locais e leituras no Quest 3 Eureka/Anorak.
Este relatório não inclui serial, boot ID completo, logs privados ou credenciais.
As novas capturas brutas permanecem fora do repositório; sua coleta não concede
autorização para publicação. Não houve boot do kernel alternativo.

## Atualizações locais

- Restaurados dois links simbólicos convertidos em texto na cópia extraída:
  `quest3/ram-first-candidate/Image` e
  `quest3/inputs/dwarves-quest3-cfi/lib/include/bpf`.
- O destino do Image foi conferido contra tamanho e SHA-256 do manifesto.
- Nove PNGs libbpf ausentes foram recuperados do upstream, aceitos somente
  depois de corresponderem exatamente aos hashes e tamanhos históricos.
- Modelo x18 e auditoria CFI compatíveis com imediatos hexadecimais do LLVM;
  modelo x18 aceita a representação explícita da instrução BTI.
- Suíte detecta LLVM instalado para executar a auditoria CFI.
- Baseline PMSG verifica tamanho declarado, formato do boot ID e marcador;
  comparação rejeita IDs malformados. Testes cobrem metadados inválidos.
- Corrigidas aspas extras no comando `su -c` do coletor somente leitura.
  O mock passou a verificar o argumento real, sem mascarar esse erro.

Resultado local: **23 testes aprovados, zero falhas, zero ignorados**.
Isso valida modelos e checagens de binários, não execução arquitetural ou boot.

## Aparelho e root

- Kernel observado: `5.10.246-gd7102a837402`; acesso root existente funcional.
- Boot ID permaneceu igual nas verificações anteriores/posteriores à coleta.
- Pstore vazio; snapshot inicialmente ausente.
- Magisk `1db2ceaf`, versão numérica `30700`, em `/debug_ramdisk`.
- Diretórios `service.d` e `post-fs-data.d` vazios, embora existam módulos
  Magisk com scripts próprios. Nenhum desses scripts foi executado manualmente.
- Magisk PID observado começou aos **69,49 s**, conforme starttime de procfs
  e `CLK_TCK=100`. Primeira habilitação da tela registrada aos **15,130 s**.
- Novos eventos de framework aos 75,806 s e tela aos 80,365 s são compatíveis
  com reinício do userspace; não demonstram novo boot do kernel.
- Dmesg preservado registra `panicreporter` iniciando aos **80,461494 s** e
  terminando com status zero aos **80,575310 s**.

Há uma janela potencial com root antes dessa execução do panicreporter, mas
não foi excluída uma execução anterior na primeira inicialização. Os nomes
post-fs-data/late_start no log Magisk não demonstram ordem antecipada no init
original. Nenhum hook early-root foi instalado ou validado.

## Snapshot bruto autorizado

Foi autorizada uma única carga temporária de `q3_ramoops_snapshot`, seguida
de coleta e remoção, sem reset ou marcador.

| Item | Resultado |
|---|---|
| Módulo | SHA-256 `403c9161a293cb6ce322c3ec0412268026c77e21b68f741c9436025f01993e2d` |
| ABI | vermagic correspondente ao kernel observado |
| Região DT | base `0xbfa00000`, tamanho 589.824 bytes |
| Transporte | 36 blocos, SHA-256 local/remoto e boot ID conferidos |
| Snapshot | SHA-256 `2848169a11cbd03c7b82a79ba2e61c2dcf580060c8146e5c6ea01e4ce2b8e233` |
| DT utilizado | SHA-256 `6e92af2fe0f34969b3b002db8573853aee510621d137f3ec43cc05e193d3dc31` |
| Cleanup | módulo ausente e interface sysfs removida; temporário apagado |
| Reset / marcador | nenhum solicitado / nenhuma escrita |

- Dmesg-0 e ftrace: payloads zerados.
- Console: ring cheio, payload de 131.060 bytes; trecho recuperado começa
  aproximadamente aos 55 s, sem cobrir a primeira inicialização.
- PMSG: tamanho lógico 712 bytes; os 130.348 bytes posteriores são zero.
- Nenhum dos marcadores conhecidos do analisador foi encontrado. Não houve
  teste de marcador novo nesta sessão.

A captura confirma o funcionamento atual do snapshot e sua remoção. Não
comprova retenção WARM, captura dos callbacks finais ou estabilidade universal.
A cópia da região viva pode concorrer com escritores.

## Console e qualidade das consultas

`/proc/sys/kernel/printk` retornou `6 6 1 7`, `ignore_loglevel=N`.
A linha de comando inclui `loglevel=6` e `console=none`, mas `/proc/consoles`
lista `ramoops-1`: não se deve concluir que o console persistente inexiste.
Mensagens informativas de nível 6 podem permanecer no dmesg sem chegar ao
console sob esse filtro. Não foi atribuído nível individual aos eventos antigos.

Uma primeira coleta foi inválida devido às aspas extras no `su`; foi preservada
separadamente e substituída por nova coleta em diretório novo após a correção.
Também foi rejeitada a saída de `dmesg --color=never`, opção não suportada no
aparelho. Alguns erros remotos vieram com retorno ADB zero: retorno zero não
substitui validação do conteúdo. O dmesg válido foi lido sem essa opção.

## Próximo passo

Validar emissão e captura de marcador **no mesmo boot**, conforme
[plano separado](../NEXT-EXPERIMENT.md). Não repetir WARM/root/coleta tardia.

Atualização posterior: esse teste foi autorizado e aprovado, sem reset.
Consulte o [relatório complementar](2026-11-16-pmsg-same-boot.md); as referências
acima a ausência de marcador descrevem a captura inicial, anterior ao teste.
