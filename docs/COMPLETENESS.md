# Escopo e completude da publicação

## Escopo atual — 2026-11-25

O primeiro envio para `ErickaTailsko/quest3-linux-port` é restrito a fontes e
documentação selecionadas. Capturas brutas, uploads, logs, pacotes, binários e
evidências privadas ficam locais; não foi criada uma Release nesta publicação.
Alguns testes dependem desses arquivos ausentes do clone público. O inventário
local e as afirmações históricas abaixo não são prova de conteúdo publicado.

## Registro histórico do empacotamento local

Foi incluído o material de projeto disponível nesta área de trabalho: fontes
atuais e históricas, probes, scripts, testes, configurações, relatórios, patches,
artefatos selecionados e todos os arquivos de upload disponíveis. Os pacotes
entregues foram preservados na release e inventariados por SHA256.

O histórico técnico foi reconstruído a partir da colaboração e dos arquivos.
O ambiente não fornece uma exportação literal completa do chat como arquivo;
não foi inventada uma transcrição. PDF/textos fornecidos são preservados.

Não foram enviados os19GiB integrais da árvore de trabalho. Toolchains,
checkouts de upstream, sysroots/pacotes de instalação, caches e intermediários
de kernel/LTO foram substituídos por revisões fixadas, receitas e manifestos.
Arquivos grandes já contidos nos pacotes de release não precisam de uma cópia
duplicada no Git. O inventário lista exclusões de reprodução e tamanhos.

Os originais de diagnósticos são apresentados como evidência, não como DT ou
config universal a aplicar a outro aparelho. Alguns relatos de boot são
ambíguos; os resultados negativos e inconclusivos foram mantidos dessa forma.

Credenciais e configurações de autenticação são a exceção explícita ao pedido
de publicar tudo. A verificação antes do commit procura material sensível sem
imprimir valores. Não foram adicionados tokens para tornar as receitas fáceis
de executar; futuras entregas externas devem usar segredos fora do Git.
