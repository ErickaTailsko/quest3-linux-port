# mem_buf — de onde vêm os intervalos que podem ser removidos

**Conclusão delimitada:** nos caminhos normais rastreados, a remoção de
subseções usa os intervalos de memória **importada/aceita do Gunyah RM**,
previamente adicionados ao Linux. Uma nova importação não consegue se registrar
sobre RAM que ainda esteja protegida por um recurso BUSY conflitante. Isso
reduz a hipótese de remoção arbitrária, mas **não prova que os nove intervalos
geométricos sejam imunes a hot-remove**.

O helper de remoção não valida sozinho essa propriedade, o DT não fornece uma
lista numérica fixa de intervalos importáveis e ainda não há inventário dos
SGLs de importação ativos no boot observado. Nenhuma nova operação ADB,
carga de módulo, pausa de CPUs, ioctl ou sondagem foi feita nesta revisão.

## Origem dos endereços

Na árvore pública fixada, `mem_buf_map_mem_s2` pede `gh_rm_mem_accept` com
validação de ACL/atributos, pedido de IPA contíguo e finalização da aceitação.
O argumento SGL solicitado é NULL: o RM escolhe os endereços e retorna o SGL.
`gh_rm_iface.c` documenta esse comportamento e repassa a resposta ao chamador.

Cada entrada retornada tem `ipa_base` e `size`; mem_buf_map_mem_s1 passa esses
valores a add_memory_subsection. São IPAs no espaço da VM, tratados como
endereços físicos locais pelo Linux. Isso não demonstra identidade com PA do
hardware em outro estágio de tradução ou em outro modelo Quest.

Não há no wrapper uma whitelist numérica de bases. A aceitação depende do
memparcel/ACL/RM e das validações subsequentes, não de copiar um endereço de
DT/Quest Pro. As restrições e políticas internas do RM/firmware não foram
reproduzidas nem completamente auditadas aqui.

## Barreiras do caminho de adição

`add_memory_subsection` exige base e tamanho alinhados a **2 MiB**, tenta
register_memory_resource e só depois toma mem_hotplug_lock e adiciona memmap.
register_memory_resource chama __request_region com SYSTEM_RAM e BUSY.

Em `kernel/resource.c`, conflito com um recurso BUSY impede essa requisição.
Um contêiner não-BUSY pode ser percorrido para criar um recurso filho. Logo,
o nome textual System RAM não deve substituir a análise de flags/procedência.
No caminho ARM64 normal de boot, request_standard_resources cria os recursos
System RAM com SYSTEM_RAM | BUSY; o texto de /proc/iomem, sozinho, não registra
todo o histórico desses recursos.

Se uma entrada falha, mem_buf_map_mem_s1 faz rollback **somente das entradas
anteriores que foram adicionadas**. Não remove a entrada que conflitou.
Assim, para uma importação nova, pareada corretamente, um intervalo que continua
ocupado por recurso BUSY não vira alvo da remoção apenas porque o RM o retornou.
Essa é uma conclusão condicional sobre o fonte, não uma reserva de páginas
adquirida pela nossa sonda ou um lock mantido durante toda observação futura.

## Quem chama a remoção de S1

| Caminho | Intervalos encaminhados |
|---|---|
| Rollback de mem_buf_map_mem_s1 | Prefixo das entradas já adicionadas, em ordem reversa |
| mem_buf_buffer_release | SGL guardado no objeto após o mapeamento S1 completo |
| Erro posterior à criação de S1 em mem_buf_alloc | Mesmo SGL importado |
| Erros após S1 em mem_buf_retrieve | SGL retornado pelo RM |
| Liberação de wrapper ACCEPT | sg_table aceito, convertido de volta para SGL |

Os dois chamadores diretos de remove_memory_subsection encontrados nos fontes
C são o rollback e o laço de mem_buf_unmap_mem_s1, em mem-buf-dev.c. O wrapper
de unmap é chamado pelos fluxos acima. O caso ACCEPT em mem_buf_vmperm_release
é diferente de LENDSHARE: o segundo recupera permissões de um DMA buffer local
via mem_buf_unassign_mem, **sem passar por esse helper de remoção de S1**.
Retorno de doação no caminho supplier também pode aceitar memória em stage-2
sem adicionar/remover subseções Linux nesse fluxo.

Emprestar/compartilhar um buffer local pode mudar permissões em stage-2 mesmo
sem apagar seu vmemmap. Portanto, excluir uma remoção de S1 não basta para
demonstrar acesso físico seguro, posse ou quiescência DMA/hypervisor.

## O DT deste Quest não desativa todos esses fluxos

No DT capturado, `/soc/qcom,mem-buf` tem:

- compatible `qcom,mem-buf`;
- capability `supplier` e VMID 3;
- nenhuma propriedade memory-region ou janela reg nesse nó.

Pelo probe do fonte, supplier não tem o bit CONSUMER. `mem_buf_alloc` e o ioctl
ALLOC exigem CONSUMER, mas **RETRIEVE não passa pela mesma barreira de
capability** no dispatcher nem no corpo de mem_buf_retrieve rastreado.
RETRIEVE ainda depende de handle de memparcel, ACLs e VM IDs válidos; isso
não é uma interface de usuário para escolher livremente uma base física.

A variável global de capability runtime não foi consultada nesta etapa. A
conclusão sobre supplier é a configuração esperada pelo fonte a partir do DT
preservado, não prova de que retrieve esteja ocorrendo ou de que não possa
ser chamado. Também não inferir atividade apenas porque os módulos estão
carregados na listagem anterior.

## Limites das garantias de pareamento

- mem_buf_unmap_mem_s1 não mantém um registro próprio de quais entradas esse
  chamador adicionou. Ele encaminha cada base/tamanho recebido.
- remove_memory_subsection verifica alinhamento e toma o lock de hotplug,
  mas não exige passar por offline_pages nem verifica um identificador de
  proprietário mem_buf. Não é uma API de consulta passiva.
- Há helpers exportados, incluindo o wrapper ACCEPT e os helpers S1. O rastreio
  cobre os chamadores na árvore pública disponível, não prova completude de
  todos os clientes binários stock ou de qualquer módulo externo possível.
- O rollback ignora os retornos individuais de remoção. No unmap, o retorno
  final é o da **última entrada**, não um agregado: uma remoção anterior pode
  falhar e uma posterior retornar zero. Isso não foi reproduzido no aparelho,
  mas impede tratar retorno zero isolado como prova de teardown integral.

Esses limites não demonstram que o driver esteja removendo RAM de boot neste
Quest, nem constituem uma reprodução de falha. Impedem, porém, transformar
o pareamento normal observado no fonte numa garantia universal da API.

## Relação com os nove intervalos do planejamento

Conferidos offline: todos estão dentro de memória declarada no DT e de System
RAM no iomem capturado, e nenhum cruza os 13 descritores CMA localizados.
Porém, o nome System RAM também é usado no registro dinâmico de uma importação.
A captura não certifica que cada recurso esteve continuamente BUSY desde o
boot, nem lista SGLs importados que já existiam no momento da leitura.

Consequentemente, **nenhum dos nove intervalos foi classificado como imune
a remoção de subseções**. Não se escolheu base nem ampliou a sonda. O inventário
dos 13 pools CMA não é um inventário de todos os memparcels/SGLs ativos.

## Evidência reproduzível e próximo requisito

- `quest3/restart-backend-design/mem-buf-range-audit.json`: hashes dos fontes,
  origem dos fluxos, DT e resultado por intervalo, mantendo gates fechados.
- `mem-buf-range-extracts.h`: quatro funções revisadas do fonte, com licenças
  e origem preservadas; equivalência de tokens conferida, ignorando apenas
  comentários/espaços.
- `test-mem-buf-ranges.py`: compila esses corpos C com mocks. Exercita conflito
  BUSY, contêiner não-BUSY, 64 bits, adjacência, sobreposição, overflow, rollback
  apenas do prefixo e após falha de remoção, forwarding e retorno da última entrada.

Os mocks não executam arch_add/remove_memory, memblock, RM, locks reais ou
alterações físicas. A suíte permanece independente de checkout .work e de ADB.
Suíte host: **38 aprovações, zero falhas ou testes ignorados**.

Antes de ampliar a sonda, falta estabelecer a procedência/lifetime de uma janela
exata: inventário consistente das importações relevantes **ou** prova de que o
intervalo de RAM de boot não é atingível por esses fluxos, incluindo caminhos
de erro e clientes aplicáveis. Ainda é necessário cobrir offline/hot-remove
normal e a sincronização completa. Nada nesta revisão autoriza usar helpers
de remoção, vetar hotplug, alocar páginas ou executar nova pausa de CPUs.
