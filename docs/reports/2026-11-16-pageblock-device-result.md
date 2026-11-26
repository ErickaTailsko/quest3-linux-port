# Amostra pageblock no Quest 3 — resultado

**Uma carga autorizada, amostra coletada e remoção confirmada.** O teste
proposto foi realizado após o usuário pedir continuidade em resposta à pergunta
de autorização. Não houve pedido de reset ou aquisição de memória.

## Resultado observado

- Uma tentativa de inserção, com módulo/hash previamente conferidos.
- 13 cabeçalhos previstos, endereços em ordem e report com formato verificado.
- Tempo medido dentro do callback: **2.604 ns (2,604 µs)**.
- CPUs online antes/depois: `0-5`; mesmo boot ID durante o teste.
- Módulo removido, interface sysfs ausente e temporário removido.
- SHA-256 report: `39cdc5359a0b2c2d8d863cdda39e312fcb09312b67c481392ee5eb53a249aa21`.

O tempo é do callback, não da pausa global ou do rendezvous stop_machine.
Esse sucesso único não demonstra estabilidade universal, ausência de efeitos
de timing ou comportamento sob todas as condições de hotplug/firmware.

| Início físico do bloco | Zona | Migratetype amostrado |
|---|---|---|
| 0x90000000 | DMA | MOVABLE |
| 0x90400000 | DMA | MOVABLE |
| 0x90800000 | DMA | MOVABLE |
| 0x90c00000 | DMA | UNMOVABLE |
| 0x91000000 | DMA | MOVABLE |
| 0x91400000 | DMA | MOVABLE |
| 0x91800000 | DMA | UNMOVABLE |
| 0x91c00000 | DMA | MOVABLE |
| 0x92000000 | DMA | MOVABLE |
| 0x92400000 | DMA | MOVABLE |
| 0x92800000 | DMA | MOVABLE |
| 0x92c00000 | DMA | MOVABLE |
| 0x93000000 | DMA | MOVABLE |

Todos os HEADs amostrados tinham PageReserved falso. Não foram verificados
todos os PFNs. O migratetype é metadado do bloco: foi lido pelo seu cabeçalho,
não inferido de flags BUDDY/ANON. Os tipos podem mudar depois que os CPUs voltam.

## Consequência

O intervalo inteiro não satisfez nesta amostra a premissa de pageblocks de
mesmo migratetype MOVABLE ou CMA exigida pelo contrato vendor revisado de
alloc_contig_range. **Não tentar aquisição da janela inteira com MIGRATE_MOVABLE,
não forçar reclassificação e não sobrescrever os blocos UNMOVABLE.**

Isso não prova que a janela seja para sempre impossível, nem identifica os
objetos residentes. A aquisição continuaria precisando de lifetime, validação
completa dos PFNs, tratamento de falhas e contrato separado de DMA/SMMU.

## Procedência: novo boot

O boot desta amostra é diferente do boot das capturas PMSG/DT/iomem anteriores.
O ID permaneceu igual entre preflight e cleanup desta operação, mas a causa e
a sequência de resets anteriores não foram estabelecidas. Não atribuir essa
mudança ao teste, ao WARM ou ao Singularity sem evidência adicional.
Os layouts históricos continuam sendo resultados offline das capturas de seu
próprio boot, não um preflight atualizado para este novo boot.

## Evidências e ferramentas

Brutos: `private-diagnostics/pageblock-stop-sample-01/`.
Resumo público sem UUID/serial: `quest3/pageblock-stop-snapshot/device-sample-result.json`.

O controlador `collect-once.py` exige reconhecimento explícito do risco, hash
fixado, saída nova e dispositivo selecionado. Registra intenção antes da única
inserção, não repete resposta incerta, respeita posse e boot ID no cleanup e
verifica remoção de módulo/temporário. Seus testes usam ADB falso e cobrem
resposta perdida, módulo preexistente, report inválido e cleanup falho.

Suíte principal: **31 aprovações**, sem falhas ou testes ignorados.

## Próxima ação, sem nova operação no aparelho

Revisar a estratégia de posicionamento: a janela fixa atual não pode ser
considerada elegível para a tentativa proposta. Investigar layouts alternativos
ou aquisição de uma região elegível com entrada/DT/descritores derivados,
mantendo os requisitos ARM64 e sem recomendar um endereço não adquirido.
Não repetir a pausa global, reservar páginas ou tentar salto automaticamente.
