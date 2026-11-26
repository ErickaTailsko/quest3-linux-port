# Futuro candidato leaf — pacote de evidências e plano de build isolado

**Plano especificado, não executado.** Nenhum helper/caller/Makefile de candidato
foi criado; nenhum build kernel/Android, module insertion, cache maintenance ou
operação no Quest ocorreu. Permanecem 69 grupos host, sem novo grupo nesta
etapa, e progresso global estimado subjetivamente em ~40%.

Continuação dos [checks de imports/conteúdo](2026-11-19-cache-leaf-import-policy-host.md).
Checks coerentes não aprovam build, caller ABI, cache, lifetime ou execução.

## 1. Escopo proposto e exclusões

O futuro artefato seria um candidato **isolado para inspeção offline**, com:

- Uma função leaf local conforme o contrato v1, sem exportá-la como API externa.
- Um caller C conhecido com declaração LP64 exata e call direto, preservando as
  proteções Kbuild. Retenção do caller sob LTO deve ser revisada explicitamente.
- Inicialização que recusa incondicionalmente a operação antes de chamar helper/
  caller, sem parâmetros que habilitem comportamento, sysfs, ioctl, worker,
  transporte, callbacks de plataforma, acesso a payload, alocação ou handoff.
- Nenhum código do loader incorporado e nenhuma referência a destinos físicos,
  MMIO, pools CMA, dispositivos ou endereços transplantados do Quest Pro.

Esse desenho não garante que uma inserção seja "sem efeitos": o próprio loader
de módulos aloca/reloca e executa inicialização. **É proibido testar carga,
inclusive esperando recusa**, sem novo escopo/autorização específicos. Não há
transferência, insmod, modprobe, rmmod, ADB, QEMU ou execução dos bytes do futuro
artefato nesta proposta de build offline.

O plano não escolhe implementação de passo de linha/errata por conveniência.
Raw CTR ou constante sem prova não fecham L11. Se uma solução exigir mudar ABI,
registradores ou dependências privadas, parar e revisar o contrato antes de
implementar; não relaxá-lo para obter um build verde.

## 2. Diretórios propostos — ainda não criados

Todos ficam em `/mnt/ssd/eris-main/`:

| Caminho proposto | Função futura |
|---|---|
| `.work/cache-leaf-candidate-src-01/` | Fontes isolados e outputs M= do candidato, sem reutilizar `quest3/module/` |
| `.work/cache-leaf-candidate-out-01/` | Cópia independente da preparação stock para O= |
| `private-diagnostics/cache-leaf-candidate-build-01/` | Intenção, inputs, comandos, logs, outputs e verificações do intento |

Nesta etapa só é criado o arquivo de evidências **do plano**:
`private-diagnostics/cache-leaf-isolated-build-plan-01/`. Não confundir esse
arquivo com um build realizado. As três pastas de candidato acima estavam
ausentes na inspeção e não foram reservadas nem inicializadas.

Uma etapa futura deve criar nomes novos com exclusividade; se já existirem,
parar para revisão. Sem clean, overwrite, reset, descarte de candidato anterior
ou continuação de intento interrompido por default.

## 3. Entradas e separação da preparação stock

Entradas locais propostas:

| Entrada | Âncora conhecida |
|---|---|
| Kernel fonte | `dbc2bc83a2b673f5d1c24ee9dadb0cd708ffda3f` |
| Alteração host existente | `scripts/extract-cert.c`, registrar diff/hash; não introduzir patches de kernel para este candidato |
| Clang/LLD | Android 14.0.7 r450784e, prebuilts `425c8149f17c8d9914bf690b4d5abe45a13fb993`; fixar também hashes dos executáveis reais |
| Preparação origem | `.work/cma-identity-stock-out/`, somente leitura nesta proposta |
| Config preparada | `e45b01529aa554bab274e7362b1a052517016314270cdd30adfa20413ea0faed` |
| Config runtime capturada | `fa0342f1b1dc12d2a723ecb1e390877b31f729480ad8328a89c1b5ae6b1f9a99` |
| Symvers fornecido | `c250004c0e4ac84ca2d83797109f08d7adf31b9c76450dd5a4fcc996b0a48078` |
| Release preparado | `5.10.246-gd7102a837402` |

Não usar config/symvers de QMP/trim3 para módulo do kernel stock. Não usar NDK
userspace ou fallback automático de compilador. A config normalizada não é
igualdade textual nem equivalência integral com o binário stock.

A preparação futura deve ser copiada para O= novo sem hardlinks que permitam
escrever no original. Revisar symlinks/referências absolutas antes de rodar
Kbuild. Registrar dependências geradas e hashes de inputs usados, incluindo
headers gerados, asm-offsets, scripts/linker scripts e perfil PGO quando aplicável.
Não deduzir cobertura transitiva completa somente de HEAD e `.cmd`.

O kernel fonte, toolchain e preparação original devem ser preservados. Comparar
hashes/estado antes e depois; diferença inesperada interrompe a revisão, sem
restauração automática que possa descartar trabalho alheio.

## 4. Gates do fluxo futuro

| Gate | Condição antes de avançar | Parar quando |
|---|---|---|
| B0 — escopo | Revisão específica dos futuros fontes isolados, init de recusa e estratégia de linha/errata | Só existe este plano; não há implementação revisada |
| B1 — inputs | Âncoras/config/release/symvers e ferramentas fixados, diretórios novos e plano de isolamento conferido | Divergência de origem, caminho ocupado, symlink inseguro ou input faltante |
| B2 — fonte/caller | Contrato ABI/registradores/retorno, PAC/BTI/SCS, ausência de endpoints e retenção LTO documentados | Dependência privada, callback/escape de helper, init capaz de alcançá-lo ou contrato ampliado |
| B3 — build offline | O=/M= novos, toolchain explícito, comandos/ambiente/PID/log/status registrados | Erro, timeout/interrupção sem conclusão conhecida ou tentativa de desligar proteções |
| B4 — artefato | ELF final e intermediários preservados, caller/call direto realmente presentes | Caller removido por LTO, tail/veneer não revisado, PAC faltante, imports inesperados ou metadados inconsistentes |
| B5 — revisão | Resultados estáticos e pendências de plataforma/lifetime separados | Tentativa de converter build/CRC/PASS parcial em autorização de execução |

Não executar `make -n`/dry-run como se fosse garantia de ausência de efeitos:
recipes recursivas/expansões podem executar trabalho. Nesta etapa nem dry-run,
preprocessamento, compilação nem link foram chamados.

O helper/caller não deve ficar acessível por endereço escapado só para evitar
dead-code elimination. Usar apenas uma estratégia de retenção explicitamente
revisada, mantendo Full LTO/CFI. Se o call não sobreviver, o intento não satisfaz
o contrato; não desligar LTO, mudar init para invocá-lo ou exportar endpoint.

## 5. Forma proposta do build — somente dados, não comando executado

O futuro alvo seria somente o módulo isolado via `tools/q3make`, com Q3_KERNEL,
Q3_OUT, Q3_LLVM, LOCALVERSION e M= explícitos e escopo `modules` do diretório
novo. Não chamar o Makefile histórico de `quest3/module/`, nem reconstruir Image,
módulos gerais ou outros candidatos como efeito colateral.

Paralelismo conservador proposto: `-j2`; registrar consumo/logs reais sem
presumir o custo do build anterior. A adaptação host de certificado, se necessária,
deve continuar sendo a já revisada; não baixar/instalar ferramentas globalmente.

Proteções obrigatórias: CFI estrito/cross-DSO, SCS/x18, Full LTO, MODVERSIONS,
stack protector e PAC/BTI conforme config. Inspecionar comandos **efetivos** e
flags conflitantes; não confiar apenas em Makefile/config declarados. Assembly
manual não é automaticamente instrumentada por flags C.

Preservar separadamente a unidade `.mod.c`: `scripts/Makefile.modfinal:27-28`
filtra CFI nessa etapa do Kbuild. Essa exceção não autoriza desproteger caller,
helper ou resolver privado. O build não pode remendar symvers nem fabricar CRC.

## 6. Pacote mínimo de evidências do intento futuro

1. **Intenção:** escopo offline, identificador/diretórios novos, gates/limites,
   exclusões e campos runtime falsos; sem hashes inventados de outputs futuros.
2. **Inputs:** fontes e Makefile completos, config preparada/runtime, symvers,
   release, revisões/diffs, executáveis e versões da toolchain, ferramentas/
   scripts e dependências transitivas efetivamente usadas.
3. **Registro de execução local:** argv/ambiente relevantes, cwd, PID/PGID,
   timestamps, logs completos e status de término conhecido. Timeout não mata
   necessariamente o build; não repetir/limpar a mesma saída após incerteza.
4. **ABI/caller:** declaração única, representação preprocessada/diagnósticos de
   tipo adequados e ligação com os mesmos inputs/comandos. Texto de protótipo
   sozinho não demonstra ABI pós-includes/macros/LTO.
5. **Outputs:** `.o`/bitcode e pré-link LTO quando disponíveis, `.mod.c`, `.cmd`,
   link scripts, metadados, ELF final, símbolos/relocações/disassembly e hashes.
   Não executar os bytes inspecionados.
6. **Revisões:** leaf estático, imports/conteúdo/política explícita, comparação de
   inputs preservados, controle negativo histórico PAC e fixtures de rejeição.

A política de imports futura deve ser revisada para o candidato mínimo, **não**
copiada dos 72 imports do loader histórico. Imports CMA/buddy/SCM/watchdog/USB/
VFS/transportes e resolução privada não fazem parte do leaf/caller isolado.
Metadados e instrumentação podem exigir imports específicos: revisar nome,
CRC/provider/tipo/namespace e necessidade real antes de fixar a política exata.
Não derivá-la automaticamente do próprio ELF para conseguir correspondência.

## Estado e próximo passo

Pacote e plano especificados; B0 ainda não concluído. Próximo passo offline:
revisar a proposta de fontes/caller inerte, retenção sob Full LTO e contexto de
linha/retorno antes de implementar/construir candidato. Este plano não é uma
receita já validada nem autorização para esses passos ou para operar no Quest.

Mesmo que um futuro build termine com sucesso, os verificadores continuam
PENDING/REJECT no escopo global, e cache físico/lifetime/entrada segura não
decorrem disso. Image CMA de 32 MiB, isolamento DMA/SMMU, CPUs, QMP/watchdog,
logs/âncora e novas autorizações operacionais permanecem gates independentes.
