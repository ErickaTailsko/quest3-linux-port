# Preparar publicação no GitHub

## Publicação de fontes — 2026-11-25

Destino público confirmado pelo usuário:
`https://github.com/ErickaTailsko/quest3-linux-port`, branch `main`.
Autenticação local via GitHub CLI, sem credenciais no projeto.

O primeiro envio é um **snapshot de fontes e documentação**, não backup integral
do workspace: fontes C/assembly/Python/shell, headers, patches, configurações,
Makefiles e relatórios selecionados explicitamente. Não inclui `.work/`,
`private-diagnostics/`, `diagnostics/uploads/`, capturas brutas, logs, pacotes,
binários compilados ou os manifestos históricos do workspace.

Os relatórios preservam referências a evidências locais não publicadas. A suíte
completa usa alguns desses arquivos; um clone público isolado não contém todos
os fixtures, toolchains, headers gerados ou artefatos necessários para reproduzir
os 69 grupos locais. Não foi demonstrado boot alternativo no Quest 3.

O scan de padrões conhecidos não encontrou credenciais no conjunto selecionado;
isso não é garantia de ausência de toda informação sensível. Nenhum cookie ou
token de autenticação faz parte do envio.

Os passos de preparação abaixo são históricos; não significam que os arquivos
privados ou pacotes citados tenham sido publicados nesse destino.

## Dados públicos e privados

- Resumo revisado da sessão: `docs/reports/2026-11-16-continuity.md`.
- Protocolo e continuidade: `docs/NEXT-EXPERIMENT.md`.
- Resultado autorizado do marcador no mesmo boot:
  `docs/reports/2026-11-16-pmsg-same-boot.md`.
- Novas evidências brutas: `private-diagnostics/2026-11-16/`, ignoradas por Git.
  Incluem saídas inválidas preservadas como evidência e novas capturas válidas.
- Evidências privadas do teste PMSG: `private-diagnostics/pmsg-same-boot-01/`.
- A autorização histórica para diagnósticos já publicados não deve ser
  estendida automaticamente a essas novas capturas.
- Não usar `git add -f` nessa pasta. `.gitignore` não remove arquivos já
  rastreados nem substitui revisão de segredos, dados pessoais e licenças.

Antes do primeiro commit, revisar `git status --short --untracked-files=all`,
selecionar explicitamente os arquivos e revisar `git diff --cached`.
Não tratar um manifesto correto como auditoria de privacidade.
Verificar limites de tamanho do GitHub; manter pacotes grandes em Releases
conforme a organização histórica. Escolher o remote e publicar apenas após
revisão. Não há credencial ou remote configurado por este procedimento.

## Verificações

```sh
python3 tools/verify-manifest.py
python3 tools/run-host-checks.py --report private-diagnostics/host-tests.json
git check-ignore private-diagnostics/2026-11-16/host-tests.json
```

Para atualizar a lista original em uma extração sem arquivos rastreados:

```sh
python3 tools/update-manifest.py --existing --include docs/NEXT-EXPERIMENT.md
```

Esse modo mantém a lista existente e adiciona somente caminhos explícitos;
recalcula hashes, portanto deve ser usado apenas depois de revisar diferenças.
Sem `--existing`, o gerador usa `git ls-files`: não executá-lo em um repositório
recém-inicializado vazio, pois isso produziria um inventário vazio. Depois de
selecionar todos os arquivos públicos, o modo Git passa a ser o apropriado.
