# Próximo experimento: emissão e captura no mesmo boot

Estado: **executado e aprovado no mesmo boot em 2026-11-16**, mediante autorização.
Resultado: [relatório do teste](reports/2026-11-16-pmsg-same-boot.md).
As etapas abaixo preservam o protocolo utilizado, não uma ordem para repeti-lo.
Não inclui reset, handoff, alteração de console, instalação de hook ou flash.

## Objetivo

Demonstrar que um marcador novo escrito em PMSG pode ser recuperado pelo
snapshot bruto no boot atual. Isso valida uma etapa do transporte diagnóstico,
não retenção através de reinício nem callbacks finais do kernel.

## Pré-condições e execução proposta

1. Confirmar ADB/root, kernel, boot ID, ramoops vinculado e módulo ausente.
2. Preservar o snapshot atual e definir novos diretórios, sem sobrescrita.
3. Revisar `quest3/ramoops-snapshot/stage-pmsg-test.py`: ele escreve um payload
   de aproximadamente 64 KiB em `/dev/pmsg0`, consumindo parte do ring. Essa
   escrita altera evidência diagnóstica e exige consentimento explícito.
4. Gerar marcador único; registrar tentativa antes da escrita e não repetir
   automaticamente se a resposta ADB se perder. Não fabricar texto de panic.
5. Conferir hash/ABI, carregar apenas o módulo RO revisado, coletar em blocos
   e remover o módulo, inclusive após falha, respeitando posse e boot ID.
6. Executar `check-pmsg-baseline.py` com DT real, metadados da escrita e captura.
7. Registrar hashes, unicidade/localização do marcador, boot ID consistente,
   integridade da captura e cleanup. Guardar brutos fora do conteúdo público.

## Aprovação e interrupção

Aprovar apenas se o marcador único estiver no ring lógico, no deslocamento
adequado, com captura íntegra no mesmo boot e remoção confirmada do módulo.
Interromper em perda de root, mudança de boot, incompatibilidade, resposta
incerta ou cleanup não confirmado. Não tentar recuperar por reset/Singularity.

Mesmo aprovado, o resultado não autoriza WARM ou `execute=1`. Um teste de
retenção exige antes resolver a captura anterior a todos os consumidores e
registrar a procedência de cada boot. Um marcador PMSG também não valida que
um printk informativo apareça no console persistente sob o filtro atual.

## Próximo passo após este resultado

Frente offline adicional: [comparação Quest Pro](reports/2026-11-16-quest-pro-reference.md).
Revisar AOP/QMP e provedores modulares do candidato, sem assumir equivalência
de SoC nem aplicar o pacote de patches Pro automaticamente.

Resolver a captura anterior a todos os consumidores do pstore, ou validar um
transporte independente, antes de propor reset. Não houve validação early-root
ou retenção WARM nesta sessão; novos testes com escrita/carga/reset exigem
planejamento e autorização próprios. Preservar o marcador atual e seus metadados.
