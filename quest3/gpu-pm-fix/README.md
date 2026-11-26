# GPU por callbacks PM — Quest 3

Compilação 5.10.246-gd7102a837402 com Clang 14.0.7, Full LTO, CFI e Shadow Call Stack mantidos.

## Alteração

O driver adreno.c desta árvore publica adreno_pm_suspend e adreno_pm_resume nos campos suspend/resume de dev_pm_ops. O loader agora acessa esses callbacks tipados pelo driver vinculado kgsl-3d, sem buscar seus nomes via kallsyms ou converter endereços para ponteiros de função.

O adaptador exige drvdata, callbacks suspend/resume e ausência de callbacks runtime_suspend/runtime_resume, como no driver correspondente. Mantém referências ao dispositivo e ao módulo. Verifica driver, tabela PM e drvdata sob device_lock antes de chamar callbacks; recusa desvinculação e estado já suspenso. A chamada de suspensão exige que o chamador mantenha o lock de suspensão do sistema e tenha congelado usuários, como no fluxo qkx_execute.

O estado de tentativa é registrado antes de suspend: mesmo uma falha parcial leva a uma tentativa de resume na limpeza. Erros de resume são propagados quando não existe erro anterior, ou registrados sem substituir o erro original. A limpeza libera as referências mesmo se a recuperação falhar. Isso é recuperação de melhor esforço; não garante restauração física exata se o driver rejeitar resume.

## Preflight e limites

O preflight independente `preflight_only=1 execute=0` agora exige também o vínculo KGSL e seus callbacks PM, mas não os executa. Continua sem staging, comandos SCM ou operações de hardware. A presença dos callbacks não garante que a suspensão real terá sucesso.

O salto kexec, ensaios 2/3, testes de CPU, warm reset e usb_log permanecem bloqueados sob CFI. Restam 18 referências a símbolos privados no loader, incluindo código QMP desativado. Veja remaining-private-symbols.md. As dependências centrais de freezer, desligamento e CPUs ainda precisam de uma alternativa validada ou integração ao kernel alvo.

## Validação

Compilação sem erros/avisos novos; CRC/BTF/configuração/CFI/SCS aprovados. Auditoria ARM64 dos helpers usa apenas imports exportados. Testes host do código de produção cobrem callbacks GPU, falha parcial, erro de resume, primeiro erro preservado, desvinculação, GPU já suspensa, driver incorreto, PM incompleto/runtime não suportado e preflight sem callbacks. Regressões USB/watchdog e rejeição de modos combinados passaram. Os testes usam mocks, não validam concorrência real nem comportamento físico da GPU. Não houve carregamento ou teste no headset.

## Aplicação

from-exported-api.patch aplica sobre o pacote anterior de APIs exportadas e passou por git apply --check. module contém os fontes completos e os três módulos. Os scripts pressupõem /workspace/quest3-build com a toolchain/árvore original. Não retire o bloqueio de CFI para testar os caminhos pendentes.
