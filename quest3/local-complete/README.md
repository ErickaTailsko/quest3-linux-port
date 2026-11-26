# Entrega local consolidada

Leia CHECKLIST.md para estados, evidências e ordem de testes no aparelho. Os módulos em module/ são para o kernel stock reproduzido 5.10.246-gd7102a837402. O kernel experimental nativo é um arquivo separado e não pode usar indiscriminadamente os módulos stock.

Esta entrega inclui as correções anteriores e a mudança de ordem SCM: preparar/validar imagens e realizar consultas antes da única alteração persistente permitida. Duas alterações SCM na mesma carga ou alteração combinada com testes/execução são recusadas. O patch incremental aplica sobre o pacote GPU-PM anterior e passou em git apply --check.

Os dez checks locais passaram. O teste x18 modela pilha/registradores usando o desassembly e usa o binário original como controle negativo; não executa instruções privilegiadas. Os testes de drivers/SCM/CPU usam mocks. Nenhum artefato foi carregado no aparelho nesta sessão.

ADB com root foi confirmado pelo usuário em seu computador; método de boot/recuperação não confirmado. device-tools contém coletor verificado e instruções. Use o arquivo compactado para preservar a indentação do Python. Nenhum teste automático deste pacote executa ADB real ou carrega módulos: a suíte do coletor usa ADB simulado.

Os scripts de build/verificação pressupõem /workspace/quest3-build, sua árvore de kernel, toolchain e entradas originais. Esses componentes grandes não estão incluídos; logs e manifestos registram os resultados. O preflight independente continua usando preflight_only=1 execute=0. A execução dependente de símbolos privados continua bloqueada sob CFI.
