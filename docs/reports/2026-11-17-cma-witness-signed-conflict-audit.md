# Witness — auditoria de conflitos assinados, sem prevenção de rollback

**Auditoria read-only implementada e testada no host: 57 grupos aprovados, zero
falhas/ignorados.** Não houve serviço instalado, rede configurada, integração
com o controlador, rebuild Android ou qualquer operação no Quest. O witness
anterior e os demais fontes/binaries foram preservados.

## O que esta etapa acrescenta

`native-supervisor/witness_audit.py` recebe somente bytes e chave pública
previamente fixada. Não abre arquivos/bancos, consulta peers, grava checkpoints,
reabre writers ou executa comandos. Reutiliza o verificador Ed25519 existente
sem alterar o witness de fixtures.

Há duas operações separadas:

1. **Auditar contra âncora anterior:** verificar a declaração-base e comparar seu
   binding com o digest que o caller já detinha; depois examinar até 32 pares de
   requisição/declaração fornecidos para o mesmo pending.
2. **Preservar/reverificar evidência de conflito:** conferir duas assinaturas
   válidas, sob a mesma chave fixada, que vinculam o mesmo pending a bindings
   diferentes. O artefato canônico contém ambas as requisições e declarações,
   fingerprint da chave, pending e hashes, com ordenação por binding.

Trocar a ordem dos dois inputs produz o mesmo artefato para aquele par. A
reverificação exige novamente a chave anterior do caller; não aprende confiança
a partir de uma chave embutida no próprio artefato.

Um binding inclui checkpoint **e contexto**. Mudar qualquer um deles para o
mesmo pending é conflito. Pending diferente ou assinatura de outra chave não
são tratados como prova de equivocalidade deste witness/registro: são inputs
estrangeiros, rejeitados nessa comparação.

## Semântica dos resultados

| Estado | Significado limitado |
|---|---|
| anchor-only-no-new-observation | Apenas a declaração-base coincidiu com o digest fornecido pelo caller |
| presented-bindings-match-no-safety-proof | Todas as declarações apresentadas coincidem com aquele binding |
| signed-conflict-detected | Foram apresentados dois bindings distintos assinados sob a mesma chave para o mesmo pending |

O terceiro caso preserva duas afirmações assinadas incompatíveis. **Não prova
causa, ordem temporal, rollback específico, identidade física do ator ou qual
história é correta.** Uma chave comprometida, clonagem de banco, política
defeituosa ou outro problema podem produzir a mesma evidência.

A auditoria mantém separadas as observations originais `publication-confirmed`
e `record-observed`. Uma observação posterior pode integrar um par conflitante,
mas não é convertida em confirmação da publicação original ou entrega ao caller.

Assinaturas duplicadas são verificadas/contadas como inputs repetidos, **não como
votos independentes**. Mesmo 31 cópias coerentes não apagam a 32ª declaração
conflitante. Não há implementação ou alegação de quorum.

## Limites demonstrados

- **História oculta:** o teste cria um fork válido, mas inicialmente fornece
  apenas a história coerente à auditoria. O resultado não exclui o fork oculto.
- **Âncora autoselecionada:** apresentar o fork como baseline com seu próprio
  digest pode produzir anchor-only. A API não autentica a origem independente
  desse digest; `anchor_provenance_verified` permanece falso.
- **Ausência/frescor:** não apresentar conflito não prova ausência global,
  completude de log, frescor, monotonicidade ou proteção contra rollback.
- **Input inválido:** falha de assinatura, âncora divergente, nonce/requisição
  incompatíveis, formato extra ou input estrangeiro rejeitam a comparação
  completa. Não retornam sucesso parcial ou permissão de recuperação.

Em **todos** os estados, `must_remain_frozen=true`; permanecem falsos proteção
contra rollback, não-equivocação, exclusão de forks ocultos, frescor, origem da
âncora, isolamento de deployment, entrega original, história de bootstrap,
ACK/importação reais, execução/admissão, replay, cleanup e retomada automática.
Não há next-checkpoint nem pin import no resultado.

Esta é detecção de conflitos **apresentados**, não mecanismo preventivo. Não
fecha o gate de âncora externa, não modifica o controlador congelado e não
autoriza consultas automáticas ao witness ou ao Quest depois de erro/incerteza.

## Testes e evidência

`test-witness-audit.py` cria bases SQLite de fixtures e chaves Ed25519 efêmeras
somente em diretórios temporários de host, depois compara os bytes assinados.
Cobre âncora anterior, declaração posterior de observação, checkpoint/contexto
conflitantes, inversão da ordem, duplicatas, input estrangeiro/inválido,
adulteração de assinatura/artefato, limites, história oculta e baseline
autoselecionado. A biblioteca de auditoria em si não faz I/O.

Fontes, relatório da suíte, log, artefato de conflito sintético, vetores públicos
e hashes são preservados em
`private-diagnostics/cma-witness-signed-conflict-audit-01/`. Nenhuma chave privada
é serializada. As chaves/vínculos são fixtures, não identidade operacional ou
checkpoint autorizado do Quest.

## Próximo gate

Continua pendente definir/revisar proteção preventiva do witness contra
rollback/equivocação, isolamento, autenticação/política do cliente e fonte
independente da âncora. Só então considerar publisher/reconciliação operacional.
Repetir assinaturas do mesmo witness ou acrescentar outro arquivo no mesmo
domínio não resolve esses requisitos.
