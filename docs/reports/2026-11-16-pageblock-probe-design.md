# Sonda pageblock: protótipo e impedimento de lifetime

Foi preparado o fonte `quest3/memory-window-probe/` para observar os 13 blocos
da janela fixa, sem aquisição de páginas. **Não foi compilado como módulo de
kernel nem carregado no Quest.** Nesta etapa não houve nova operação ADB.

## Evidência que alterou o plano

A configuração stock contém MEMORY_HOTPLUG=y e MEMORY_HOTREMOVE=y. A tabela
Module.symvers fornecida não exporta get_online_mems/put_online_mems, embora
a fonte pública declare essas funções para proteger acesso à memória online.
Um pfn_valid inicial seguido de acesso sem proteção não prova que os metadados
continuem vivos durante hot-remove.

Por isso o protótipo retorna EOPNOTSUPP nessa configuração **antes de tocar os
PFNs**. Ele não tenta acessar locks privados ou usar notifiers como substitutos
sem contrato comprovado. Não há recomendação de desabilitar hotplug no stock.

O fluxo de varredura foi escrito para permitir revisão e testes em host, mas
está deliberadamente bloqueado no aparelho atual. Não se deve apresentar o
trabalho como identificação realizada dos tipos dos 13 pageblocks.

## Testes realizados

O teste compila o fonte C real contra stubs nativos, cobrindo recusa hotplug
e placa incorreta antes de acesso, PFNs inválidos/device, tipos/zonas uniformes
ou mistos e páginas reservadas. O ramo sem hotplug é uma simulação, não uma
propriedade do stock observado. A suíte tem **29 aprovações**.

## Continuidade

É necessário demonstrar um mecanismo de lifetime/sincronização compatível com
as APIs stock antes de produzir uma sonda para carga real. Há duas restrições
independentes: observar metadados com segurança e adquirir páginas sem violar
o protocolo do sistema. Nada autoriza pular direto para alloc_contig_range,
reinterpretar tipos migratórios ou testar o salto.

Os tipos pageblock permanecem desconhecidos. A observação RO anterior de
SLAB/PGTABLE/mapcounts continua válida apenas como amostra dinâmica. Logs
antecipados, CPUs e DMA/SMMU seguem pendentes, independentemente desta sonda.
