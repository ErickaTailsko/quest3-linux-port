# CMA padrão — plano de identidade sem aquisição de páginas

> Atualização posterior: [protótipo implementado e testado com mocks](2026-11-17-default-cma-identity-prototype.md).
> As referências abaixo à implementação ainda por escrever registram a etapa
> do plano. O [build ARM64](2026-11-17-default-cma-identity-build.md) também foi
> concluído depois; a [revisão de recuperação](2026-11-17-cma-transport-recovery-review.md)
> corrigiu cleanup após timeout. Nenhum transporte real habilitado ou execução no Quest.

**Revisão e modelo host concluídos; experimento runtime não executado.**
Não foi preparado/carregado novo módulo, feita operação ADB, chamado alocador
ou alterado o loader. Este plano não reutiliza a autorização já consumida da
consulta de descritores. Uma futura execução requer autorização específica.

## Pergunta limitada

O ponteiro exportado `dma_contiguous_default_area` é não nulo e idêntico ao
`priv` do descritor de `/reserved-memory/linux,cma`, cujo nome, propriedades
e tamanho correspondem ao pool de boot esperado? O accessor exportado
`cma_get_name` confirma `linux,cma` para esse mesmo objeto?

O resultado seria apenas **identidade observada nesse boot e instante**.
Não significa pool ativo/com bitmap utilizável, páginas disponíveis, ausência
de clientes, posse de RAM, imunidade completa a hot-remove ou autorização de
alocação. A região observada anteriormente não é endereço fixo deste plano.

## Racional e limites do fonte

Revisão: `dbc2bc83a2b673f5d1c24ee9dadb0cd708ffda3f`. Hashes dos fontes CMA,
DMA e cabeçalhos já estão em
`quest3/restart-backend-design/stock-allocation-source-review.json`.

- `kernel/dma/contiguous.c:408–445`: rmem_cma_setup é init-only, exige reusable
  e ausência de no-map, cria a área com o nome do descritor e, quando existe
  linux,cma-default, atribui o mesmo objeto ao ponteiro padrão e a rmem->priv.
  Um parâmetro CMA de linha de comando pode desviar esse caminho: conferir
  propriedades/nome não substitui a comparação dos ponteiros.
- `mm/cma.c:48–66`: as áreas estão em array estático; cma_get_name retorna
  cma->name, sem adquirir referência ou lock de lifetime. **Não o chamar num
  ponteiro nulo ou diferente do priv validado.**
- `drivers/of/of_reserved_mem.c:425–440`: lookup retorna um elemento do array
  de descritores por nome. Não é uma operação de posse nem um pin da RAM.
- A config stock arquivada tem OF_DYNAMIC e OF_OVERLAY desabilitados e
  páginas ARM64 de 4 KiB. A proposta depende dessa configuração estática e
  da revisão de lifetime/ABI; não é portátil automaticamente a outro stock.
- `include/linux/cma.h:37` e `include/linux/dma-map-ops.h:107` fornecem os tipos
  públicos. Não copiar struct cma privada nem chamar cma_get_base/size não
  exportados. Não procurar símbolos por kallsyms ou contornar CFI.

READ_ONCE e uma segunda observação só detectam algumas inconsistências;
**não são locks, referências, prova contra ABA ou sincronização com hotplug**.
Se a justificativa estática não se aplicar ao stock exato, interromper antes
da carga. CRC/MODVERSIONS e asserts de layout ajudam, mas não provam toda a
equivalência binária. A conclusão de identidade não encerra o gate de lifetime
da futura alocação.

## Gates antes de preparar qualquer execução

1. Rever código de uma implementação ainda a escrever e seus testes de C,
   parser e controlador. O modelo Python desta etapa não substitui isso.
2. Preservar CFI estrito, SCS, Full LTO e MODVERSIONS no build do módulo;
   conferir imports/CRCs contra stock e layout público de reserved_mem como
   na consulta anterior. Nenhum import de cma_alloc/cma_release/buddy/ACR.
3. Conferir kernel release/config, DT e identidade do boot antes e depois;
   a evidência arquivada de outro boot não satisfaz o preflight runtime.
4. Preflight de ausência de módulo/sysfs/temp homônimos, hash do arquivo a
   transferir, relatório bounded e captura privada sem serial/UUID públicos.
   Não sobrescrever artefato inesperado nem remover módulo preexistente.
5. Obter consentimento para **uma carga da consulta de identidade**, incluindo
   seus efeitos de carga/descarga. Não pedir alocação de páginas de payload,
   pausa de CPUs, migração, cópia de payload ou handoff no mesmo consentimento.

“Sem alocação” aqui significa **sem chamar alocadores de páginas de payload**:
insmod, estruturas de módulo e criação de sysfs têm efeitos e alocações normais
de metadados. Não apresentar a futura carga como operação puramente RO.

## Sequência proposta, uma vez e sem fallback

Em contexto de processo, consultar somente `/reserved-memory/linux,cma`:

1. Exigir plataforma Quest 3/Anorak, config/ABI revisados e opt-in explícito.
2. Localizar o nó exato; exigir available, shared-dma-pool, reusable,
   linux,cma-default, ausência de no-map e size de 32 MiB. Não enumerar pools
   dedicados nem escolher outro se esse nó falhar.
3. Lookup do descritor público; conferir nome linux,cma, base não nula e
   alinhada em 4 MiB, size de 32 MiB, fim dentro dos 4 GiB baixos sem overflow,
   ops e priv presentes. Não chamar callbacks ops.
4. Ler uma vez o ponteiro padrão e priv; comparar identidade não nula antes
   de consultar nome. Não imprimir ponteiros virtuais, nem usar endereço físico
   antigo como condição de sucesso ou destino.
5. Consultar somente cma_get_name no objeto correspondente; comparação limitada
   ao nome esperado e terminador, sem copiar string arbitrária para o relatório.
6. Reobservar ponteiro padrão e priv. Se mudaram, rejeitar; se não mudaram,
   manter os limites de snapshot acima. Devolver referência OF em todo caminho.
7. Publicar somente relatório imutável e limitado com versão de esquema,
   propriedades validadas, igualdade/nome, erro e flags explicitamente falsas:
   allocator_called, availability_proven, ownership_acquired,
   allocation_experiment_ready e boot_ready. Leitura de sysfs não repete consulta.

Qualquer falha deixa identidade não aprovada. Null, nome inesperado, divergência
de ponteiros/propriedades, erro de ABI ou relatório truncado não autorizam
fallback, accessor adicional, varredura de PFNs ou teste pequeno de CMA.

## Captura, interrupção e limpeza

- Controlador de execução ainda não implementado. Deve persistir intenção antes
  da carga e consumir a tentativa antes de insmod; nunca repetir após timeout,
  perda de ADB ou resposta incerta. Não disparar reboot automático.
- Se o estado for incerto, marcar resultado indeterminado e reconciliar presença
  do módulo/sysfs no mesmo boot; isso não autoriza nova inserção. Mudança de
  boot invalida o encadeamento, mesmo havendo relatório antigo.
- Após captura e validação, descarregar somente o módulo desta tentativa,
  conferir ausência em módulos/sysfs e remover somente seu arquivo temporário
  conhecido. Desconexão ou falha de rmmod deixa limpeza não confirmada.
- Falha de init deve devolver a referência OF e quaisquer metadados criados;
  exit deve remover sysfs/kobject, sem liberar páginas de payload inexistentes.
  Sucesso de cleanup não converte relatório rejeitado em identidade aprovada.

Mesmo sucesso de identidade e limpeza não libera o experimento de aquisição.
O [trim3](2026-11-17-usb-trim3-result.md) cabe com 31,25 MiB, mas o pedido
arredondado ocupa os 32 MiB nominais inteiros. Continuam pendentes impacto nos
clientes, disponibilidade, lifetime aplicável, rollback e autorização de uma
eventual chamada de alocador. Não propor exaurir o pool como simples diagnóstico.

## Modelo e testes desta etapa

`quest3/restart-backend-design/cma_identity_model.py` usa somente objetos fake.
Não lê dispositivo/arquivo de captura e não produz evidência de identidade real.
`test-cma-identity.py` cobre gates estritos, nó/descritor ausente, limites físicos,
identidade nula/divergente, accessor somente após igualdade, reobservação,
devolução OF e impossibilidade de repetir uma transação aceita ou rejeitada.
No caminho aceito, disponibilidade/posse/prontidão permanecem falsas.

Suíte host: **42 aprovações, zero falhas e zero testes ignorados**. Próximo
marco possível: implementar e testar a consulta/controlador somente no host,
submetendo o código e o escopo à revisão antes de pedir carga no Quest.
