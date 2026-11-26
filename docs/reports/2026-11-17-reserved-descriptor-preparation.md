# Consulta de descritores — módulo preparado, transporte interrompido

**Atualização:** transporte retomado no mesmo boot, caminho temporário antigo
confirmado ausente e consulta única concluída com cleanup. Os 13 descritores
foram localizados; [resultado atual](2026-11-17-reserved-descriptor-result.md).
O bloqueio e a limpeza pendente abaixo registram a etapa histórica anterior.

**Nenhum descritor foi consultado no kernel: houve zero tentativas de
inserção.** ADB desconectou durante o envio do arquivo, antes de `insmod`.
O possível arquivo temporário parcial permanece sem confirmação de remoção.
As 13 bases físicas continuam não localizadas.

## Autorização e preparação

Após pergunta explícita sobre preparar/revisar/carregar uma vez o módulo RO,
com risco de travamento informado, o usuário respondeu “continue”. O escopo
aceito foi uma consulta dos 13 descritores e limpeza, sem pausa de CPUs,
sondagem de PFNs/pageblocks, alocação/migração, conteúdo físico ou reset.

Fontes, controlador e testes em `quest3/reserved-descriptor-query/`. O módulo
exige `inspect=1`, caminhos fixos e board Eureka/Anorak. Usa somente APIs OF
tipadas exportadas e acesso aos campos do descritor público; não invoca ops
ou usa estruturas privadas CMA. Presença de ops/priv, nomes, tamanhos,
alinhamento, limites e sobreposição são verificados. O relatório sysfs 0400
é uma cópia estática, não uma nova consulta a cada leitura.

Build separado concluiu com retorno zero:

- SHA-256 módulo: `6ac24447b03474a6343a25fe19871a43b0a9e6f383c2e6301ff7b5803c80d066`.
- Tamanho: 270.904 bytes.
- Vermagic: `5.10.246-gd7102a837402 SMP preempt mod_unload modversions aarch64`.
- Vinte CRCs importados conferidos com a tabela stock fornecida.
- CFI/SCS/Full LTO, stack protector e `-ffixed-x18` presentes nos flags;
  `__cfi_check` presente no binário.
- Struct pública `reserved_mem`: sizeof=56, offsets ops/base/size/priv
  24/32/40/48 conferidos por asserts de compilação, não por prova do binário stock.

Foi reutilizado o ambiente stock preparado, não um candidato QMP/trim.
A configuração preparada normalizada difere da captura stock em metadados
de ferramentas, LOCALVERSION_AUTO e opções desabilitadas ausentes na árvore
pública; os hashes distintos foram registrados. Não se afirma equivalência
binária completa ou que CRCs comprovem todos os layouts internos.

Artefatos, autorização e resultado dos testes anteriores ao envio preservados
em `private-diagnostics/reserved-descriptor-prepared/`. Metadados revisados:
`quest3/reserved-descriptor-query/build-verification.json`.

## Tentativa real de transporte

Evidência privada: `private-diagnostics/reserved-descriptor-query-01/`.
O controlador confirmou root, release, hashes do config.gz/DT conhecidos,
boot válido, máscara CPU `0-5`, ausência prévia do módulo e do caminho sysfs,
e ausência do novo caminho temporário gerado para este envio.

`adb push` retornou falha. O controlador interrompeu antes de verificar hash
remoto ou marcar intenção de inserção: `insertion_attempts=0`. A tentativa
de ler boot ID para limpeza recebeu retorno 255; as verificações seguintes
ficaram bloqueadas. ADB continuou sem aparelhos nas verificações posteriores.

Não houve comando insmod, rmmod, pausa de CPUs, alocação, reset ou handoff.
Não atribuir a desconexão a execução deste módulo, que não foi iniciada.
Não inferir se houve reset do aparelho ou só queda de transporte. Boot atual
e presença/remoção do arquivo parcial não estão confirmados.

O controlador exato da tentativa foi preservado como `controller-attempt.py`
nos brutos. Ele registrou o retorno de push, mas não seu stdout/stderr;
essa limitação não permite diagnosticar a causa exata da falha.

## Correção preparada, ainda sem execução no aparelho

O controlador deixou de usar adb push e adotou a técnica já usada no projeto:
blocos base64 de 4 KiB, escritos por offset em arquivo único, sem retries.
Tamanho e SHA-256 remotos devem conferir antes de qualquer insmod. Retornos
das escritas ficam no log; a confirmação integral não depende só de exit zero.
Isso não recuperou a conexão, não enviou novos blocos e não realizou inserção.

Testes host abrangem corpo C real com mocks, consulta limitada, referências OF,
setup incompleto, limites/overflow e controlador com ADB simulado: consentimento,
quoting, hashes, saída existente, boot alterado, módulo preexistente, chunk
parcial, resposta de inserção perdida e cleanup sem repetir insmod.
Suíte final: **36 aprovações, zero falhas ou testes ignorados**.

## Condições para retomar

1. Reconectar o Quest sem solicitar resets ou novas tentativas de root apenas
   para este teste. Confirmar Android/ADB/root estáveis.
2. Conferir boot contra o registro pré-envio e verificar ausência do módulo e
   sysfs. A tentativa preservada tem zero inserções; não pressupor esse fato
   para qualquer outra operação futura.
3. Avaliar e remover somente o caminho temporário exato desta operação,
   confirmando sua ausência; não fazer limpeza por glob ou de arquivos alheios.
   Se o boot mudou, registrar a diferença e revisar procedência/config/DT antes
   de qualquer ação, sem rmmod automático em outro boot.
4. Só depois retomar o envio revisado e a **única** inserção autorizada, com
   relatório e remoção conferidos. Nenhuma inserção incerta pode ser repetida.

Não há base selecionada, destino adquirido ou nova sondagem proposta. O próximo
bloqueio imediato é restabelecer transporte e fechar a limpeza parcial.
