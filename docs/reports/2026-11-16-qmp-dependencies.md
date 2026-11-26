# Auditoria de disponibilidade AOP/QMP — 2026-11-16

**Atualização posterior:** a lacuna identificada abaixo foi corrigida no
artefato de um candidato separado, compilado e checado, ainda sem boot.
Veja o [resultado do build](2026-11-16-qmp-build-result.md). As descrições do
candidato inicial e do fragmento não aplicado registram a etapa da auditoria.

## Conclusão

**O alvo mínimo atual não disponibiliza os drivers AOP/QMP identificados.**
O candidato tem `CONFIG_MSM_QMP=m` e `CONFIG_QCOM_AOSS_QMP=m`, enquanto o CPIO
USB mínimo contém apenas BusyBox/init e diretórios/dispositivos básicos: não
há `.ko`. Seu `/init` não executa insmod/modprobe. A presença dos nós no DT
não torna esses provedores disponíveis.

Isso é uma lacuna demonstrada de disponibilidade, não prova de que corrigir
esses dois símbolos basta para boot, nem de que todos os consumidores sejam
necessários para o alvo mínimo. Não foi alterado o Image/config publicado.

## Fontes revisadas

Revisão pública fixada no projeto:
`facebookincubator/oculus-linux-kernel`, commit
`dbc2bc83a2b673f5d1c24ee9dadb0cd708ffda3f`.

Arquivos baixados para `.work/qmp-audit/`, ignorados pelo Git. A revisão pública
não é equivalência binária comprovada ao kernel do fabricante no aparelho.

| Arquivo | SHA-256 |
|---|---|
| drivers/mailbox/msm_qmp.c | `e3bb6f3e6bbc7f47dae780d40d2e9a07b860a9519eb368013c19b9db5e4556d3` |
| drivers/mailbox/Kconfig | `8d45dde470d8990cb929ac6ea427039aee27862d32426a943dbbe00d8317eedd` |
| drivers/mailbox/Makefile | `584873e6e2715377b3437224c49c152e9d8832e4b7aa85114ff4d446a5ca5a9e` |
| drivers/soc/qcom/qcom_aoss.c | `90655ebf973345f490f5c6a223400b4dd213560069b9446b421b23526841d956` |
| drivers/soc/qcom/Kconfig | `543f4b705abadefa5845273f2d645f4d0a3713edd8efcbe11cd5a642ea91a189` |
| drivers/soc/qcom/Makefile | `df31ffd3570c5fff97ae1ca4fa7ad6b0fbef32547b588c1e6337fb599efe82f1` |

## Caminho real do AOP no DT Quest 3

```text
consumidor mboxes
  -> /soc/qcom,qmp-aop (qcom,qmp-mbox; MSM_QMP)
     -> propriedade qcom,qmp
        -> /soc/power-controller@c300000
           (qcom,anorak-aoss-qmp; QCOM_AOSS_QMP)
```

Na fonte revisada, `qmp_mbox_probe()` escolhe `qmp_shim_init()` quando existe
`qcom,qmp`. O shim obtém o backend por `qmp_get()` e envia via `qmp_send()`.
Essas funções são exportadas por `qcom_aoss.c`, cujo probe chama `qmp_open()`.
Logo, o estado herdado/handshake do AOP precisa de revisão nesse backend,
não apenas no caminho de memória compartilhada legado de `msm_qmp.c`.

Consumidores `mboxes` diretos encontrados no DT capturado:

- `soc-sleep-stats@c3f0000`;
- `sys-pm-vx@c320000`;
- `qcom,gmu@3d69000`;
- `qcom,cnss-qca6490@b0000000`.

O segundo provedor, `/soc/qcom,qmp-tme`, não possui o mesmo redirecionamento
`qcom,qmp` no DT analisado; seu consumidor direto é `qcom,tmecom-qmp-client`.
Não confundir TME com o backend AOP nem assumir igual protocolo de adoção.

As referências `mboxes` foram percorridas usando phandle e `#mbox-cells`, não
buscando qualquer inteiro coincidente em clocks/argumentos. A lista cobre
dependências mailbox diretas, não toda dependência transitiva ou dinâmica.
O status próprio desses nós é okay; isso não substitui revisão de ancestrais,
drivers consumidores, recursos, firmware ou ordem real de probe.

Evidências locais: `private-diagnostics/qmp-audit/dt-dependencies.json` e
`initramfs-entries.json`. Nenhuma nova operação no Quest foi necessária.

## Proposta de correção e critérios

### Recursos do backend e dependência IPCC

Revisão posterior do DT e das fontes completas confirmou:

```text
MSM_QMP (shim AOP)
  -> QCOM_AOSS_QMP (power-controller@c300000)
     -> QCOM_IPCC (mailbox + domínio de interrupções)
        -> controlador de interrupções do SoC
```

`qcom_aoss.c:qmp_probe` mapeia o recurso MMIO do DT, solicita mailbox e IRQ,
e chama qmp_open antes de registrar relógio QDSS e domínios de energia.
O IPCC registra mailbox/domínio IRQ e seu driver usa arch_initcall.
Esses fatos não garantem que o probe ou as interrupções funcionem após handoff.

Na configuração separada em compilação: QCOM_IPCC, ARM_GIC_V3, MAILBOX,
OF_IRQ, OF_ADDRESS e PM_GENERIC_DOMAINS já são `y`, além dos dois provedores
QMP promovidos a `y`. Não foi identificada nova dependência modular nesse
trecho direto. Isso não fecha todas as dependências transitivas ou consumidores.

O nome do nó IPCC não deve ser usado como endereço: o recurso `reg` da captura
difere do sufixo textual do nome do nó. Nenhuma escrita MMIO foi realizada;
os drivers devem obter e traduzir recursos do DT pelos frameworks apropriados.

Fonte `drivers/mailbox/qcom-ipcc.c`, na revisão fixada, SHA-256:
`5ef19ec0d05daa8756c7d01f2f6cb6d0ba1a4601f1eb34987db45799fb5e6d05`.
Registro local: `private-diagnostics/qmp-audit/backend-resources.json`.
As checagens de configuração e de artefatos passaram a exigir IPCC e GICv3.

Na fonte revisada, a remoção de AOSS chama qmp_close e publica estados DOWN;
o driver não declara callback shutdown. Não confundir remove, shutdown e
preservação de link: a cadeia efetivamente executada no Android antigo ainda
precisa ser estabelecida, e desligar um provedor manualmente não é teste RO.

### Configuração proposta

Fragmento de revisão: `quest3/qmp-audit/builtin-proposal.config`, com
`QCOM_AOSS_QMP=y` e `MSM_QMP=y`. Não foi mesclado à configuração atual.

Próximos passos de build, em nova saída e sem substituir artefatos publicados:

1. Obter árvore completa na revisão fixada e toolchain documentada; os arquivos
   isolados desta auditoria não são suficientes para compilar um kernel.
2. Mesclar o fragmento à config RAM-first e rodar olddefconfig, verificando
   dependências Kconfig, sobretudo MAILBOX, COMMON_CLK e PM do backend AOSS.
3. Revisar `qmp_open`, falhas de handshake e recursos do backend Anorak para
   estado herdado; não aplicar automaticamente `qkx_qmp_adopt` do Pro.
4. Compilar kernel alvo com proteções preservadas. Confirmar os drivers
   embutidos e a cobertura de dependências, sem alegar boot por isso.
5. Guardar novos hashes/config/diff separados e repetir as verificações host.

Disponibilidade de driver, compatibilidade do handshake e quiescência do kernel
antigo são três contratos distintos. Esta auditoria fecha apenas o diagnóstico
de disponibilidade do candidato atual. Logging inicial, CFI, CPUs, posse de RAM
e DMA/SMMU continuam bloqueando um ensaio de salto.
