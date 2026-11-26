# Histórico técnico reconstruído

Este registro organiza as decisões da colaboração; os documentos e uploads
originais foram preservados para auditoria. Não é uma exportação literal do chat.

1. **Escopo e ambiente.** Selecionado o repositório ErickaTailsko/eris.
   Referências Quest 2 SteamOS e quest-kexec; bootloader do Quest 3 travado,
   root Singularity. Pedido de primeiro alvo mínimo: BusyBox em RAM, sem
   montagens de blocos, rede USB e log recuperável.
2. **Configuração do aparelho.** A configuração inicial de build usava
   LTO_NONE, enquanto o aparelho tinha Full LTO, CFI estrito, CFI shadow,
   SCS e MODVERSIONS. Foi recuperado `/proc/config.gz` e configurado Clang
   Android14/LLD/integrated assembler corretos, preservando as proteções.
3. **Build e BTF.** PGO exigia vmlinux.profdata; o arquivo existia na fonte.
   pahole1.32 omitia vfs_truncate por endereço ambíguo associado a CFI.
   O pahole adaptado gerou BTF e permitiu BTFIDS/SORTTAB/SYSMAP/Image/módulos.
   Os logs anteriores e os casos negativos foram preservados.
4. **Loader.** Corrigido o retorno de x18 com LR, mantendo frame96 bytes.
   Resolver privado bloqueado sob CFI e usb_log privado bloqueado com -95.
   Não se usaram __nocfi, CFI permissivo ou endereços forjados para o salto.
5. **SCM/plataforma.** Portadas APIs SCM exportadas. O DT real usa arrays
   core-hang de seis CPUs; leitura validada, escrita legado bloqueada.
   USB, watchdog e GPU receberam referências, callbacks tipados, tratamento
   de falhas e rollback. A desativação segura do watchdog não tem inversa.
6. **Preflight.** Criado caminho somente de leitura independente de staging,
   recusando15 combinações conflitantes antes de acessar dispositivos.
   Carregamento e remoção desse caminho passaram no aparelho.
7. **CPUs/restart.** Teste individual CPU1 passou. Protótipos multi-CPU
   permaneceram bloqueados por concorrência/ordem de desligamento.
   EFI runtime/reset não estava disponível. Analisadas fases reboot,
   syscore e restart: retorno do notifier não aborta kernel_restart;
   callback final é atômico; syscore já vem após device_shutdown/SMMU.
8. **Persistência inicial.** Marcador console e PMSG não foram recuperados
   após reboot/root. Init inicia panicreporter em boot_completed; análise
   estática da biblioteca revelou descarte/purge de logs sem panic.
   Isso não explica sozinho todo o desaparecimento do PMSG.
9. **BusyBox/alvo.** Compilado BusyBox1.36.1 estático ARM64 e CPIO gzip.
   Verificações independentes de ELF, CPIO, applets e sintaxe em QEMU.
   Kernel RAM-first integra33 provedores/imports, mantendo CFI/SCS/LTO.
10. **USB mínimo.** DT2 high-speed peripheral, UCSI desabilitado e grafo de
    papel desconectado; preservados os dois PHYs necessários ao driver MSM.
    O writer binário evitou bug de escapes do dtc textual. Init ECM não
    monta discos; testes usam filesystem e APIs simulados.
11. **Transporte de arquivos.** Downloads internos e Catbox falharam.
    Pixeldrain foi utilizado com verificação de download/hash. ADB apresentou
    EOF e arquivos ausentes; criados coletores e uploaders em blocos pequenos,
    com offset idempotente e confirmação final SHA256.
12. **Posicionamento.** Image novo tem text_offset0, incompatível com
    entrada fixa antiga0x90080000. Implementada entrada0x90000000, mantendo
    suporte ao offset0x80000. Janela52MiB corroborada por iomem e DT.
    Ajustados `/chosen` e bootargs em cópias verificadas do DT do usuário.
13. **Pstore detalhado.** Serviço logcatd configurado não provou atividade.
    Busca de FDs encontrou nenhum pstore aberto; diretivas de console do
    health-service pertencem ao modo charger, não ao serviço Android normal.
14. **Captura bruta RO.** Construído e testado módulo limitado ao ramoops
    do DT, driver vinculado e atributos de mapeamento conhecidos. Snapshot
    imutável transferido e validado, módulo removido. Marcadores antigos
    ausentes; resultado inicial sozinho não distinguiu perda/sobrescrita.
15. **Marcador com preenchimento.** Escrito por `/dev/pmsg0`, usando64KiB
    de padding e token único. Referência COLD confirmou token na posição68262.
    Após reboot, PMSG só712 bytes e cauda inteira zerada. Confirmada ausência,
    sem atribuir a limpeza conclusivamente ao firmware.
16. **Política reset.** Leitor de globais exportadas mostrou COLD0/panic-1.
    Guard opt-in usa cmpxchg para WARM e restaura no unload se ainda coincide.
    Ciclo real COLD→WARM→COLD passou, sem reset nem chamada de firmware.
17. **Teste WARM.** Nova referência na posição66248. Controlador validou
    estado e solicitou reset uma vez, com ack ADB0. O Singularity causou
    resets completos adicionais ao tentar root. Root voltou na quinta
    tentativa; captura final sem marcador, cauda zerada. O experimento não
    isola a retenção do primeiro reset WARM e permanece inconclusivo.
18. **Publicação.** Pedido de publicar fontes, checklist e todo o material.
    Confirmado repositório público vazio e autorização adicional para incluir
    diagnósticos brutos. Credenciais excluídas; grandes builds/depêndencias
    substituídos por fontes fixadas, receitas e artefatos em release.

Não houve primeiro boot validado, flash de partições ou instalação automática
de quest-kexec nessa sequência. Os diversos resets foram testes do kernel
Android e recuperação de root, não boot do kernel candidato.
