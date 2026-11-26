# Quest 3 — caminho USB mínimo em modo periférico USB 2.0

Implementação e testes offline concluídos; enumeração no aparelho pendente.
Este pacote NÃO habilita o salto entre kernels. Não é imagem de flash.

## Conjunto de artefatos
Reutilizar Image 5.10.246-gd7102a837402-q3-ram-first já compilado:
SHA256 cee2f89539dba8ec4c87351ccef350ba2a614dfd2b47778588c95c580e96234d
Pacote desse kernel: https://pixeldrain.com/u/ueVwKUxV
Substituir o initramfs anterior por quest3-usb2-minimal.cpio.gz deste pacote.
Gerar o DTB de destino LOCALMENTE com prepare-dtb.py. Nenhum DTB original ou
resultante foi incluído no upload público. O script não acessa ADB nem partições.

## Mudanças do DT
Apenas sete propriedades: remover usb-role-switch no glue MSM e no DWC3;
dr_mode=peripheral; maximum-speed=high-speed; desabilitar o nó UCSI; remover
remote-endpoint nas duas extremidades de seu vínculo com USB. Nós, phandles,
reguladores, clocks, IRQs, IOMMU, reservas e demais propriedades preservados.
Não desabilitar/remover o PHY SS: o probe do glue requer ambos os objetos PHY
mesmo quando opera só a high-speed; a inicialização SS é condicional à velocidade.
A seleção de papel deixa de esperar UCSI/ADSP, mas os fornecedores de clocks,
reguladores/RPMh e estado de firmware herdado ainda precisam funcionar.
O software assume VBUS presente no modo periférico; isso não mede tensão nem
implementa política USB-C/PD ou carregamento. Primeiro teste será em conexão
direta com PC fornecendo VBUS, nunca como host/OTG ou hub de periféricos.

## Gerar e conferir o DTB no computador — sem root
Requer Python 3. Opcionalmente, usar dtc da árvore de kernel para verificação
binária independente. Ajustar o caminho do DTB de entrada:

python3 prepare-dtb.py --input "$HOME/quest3-live.dtb" --out "$HOME/quest3-usb2-peripheral.dtb" --dtc "$HOME/quest3-llvm-config.bOyxO7/scripts/dtc/dtc"

O destino deve ser novo. A saída inclui JSON com hashes/mudanças e arquivo de
avisos dtc. Verifica modelo/compatíveis, grafo, objetos PHY e ausência de políticas
externas inesperadas. Recusa mudança em qualquer propriedade fora da lista.
usb2-peripheral.dtsi é a equivalência para revisão de fonte, NÃO um DTBO.
Não usar DTB -> DTS -> DTB nesse dtc antigo: encontramos alteração indevida de
qcom,init-voltage por escape octal; o comparador recusou a saída. O patcher binário
preserva os bytes e foi validado com dtc -I dtb -O dtb, que evita esse problema.
Não acrescentar usb3gen2en=1 aos argumentos do kernel: sobrescreve a velocidade.

## Initramfs
BusyBox estático ARM64 já verificado. /init monta só sistemas de arquivos em RAM,
confere propriedades USB do DT, exige um único UDC a600000.dwc3 com maximum_speed
high-speed e configura somente ECM. Descritor bcdUSB=0x0200 e max_speed=high-speed.
Endereço do alvo 10.42.0.2/24, host 10.42.0.1/24; MAC host 02:51:33:00:00:01.
Sem DHCP, Wi-Fi, default route ou montagem de discos. Telnet de desenvolvimento
sem autenticação na interface USB: usar link direto isolado.
A falha de DT/UDC/bind interrompe o fluxo antes de configurar rede. Nenhum reset
ou alteração de watchdog é executado. Os logs /tmp são voláteis; pstore continua
sem retenção comprovada no aparelho. Sem DT/periférico corretos o init não avança.

## Verificações executadas
- DT real: sete diferenças permitidas; todos os outros valores e reservas iguais.
- Transformação idempotente; rejeita modelo/PHY/grafo/host/extcon inesperados,
  blobs truncados e sobrescrita do destino; dtc valida saída binária.
- Função REAL dwc3_msm_check_extcon_prop testada com APIs simuladas: periférico
  inicia sem evento UCSI; role-switch aguarda evento; host e erro extcon contrastados.
- Fluxo do init em filesystem simulado: sucesso, DT inválido, UDC ausente,
  incorreto/múltiplo e bind recusado; sem mounts ou interfaces reais nesses testes.
- CPIO/ELF e applets conferidos; sintaxe/aritimética em QEMU ARM64; initramfs
  regenerado com o mesmo SHA256. Não houve boot de kernel ou teste USB em QEMU.

Executar novamente, conforme ferramentas locais disponíveis:
sha256sum -c SHA256SUMS
python3 test-usb-role.py
python3 test-init.py
python3 verify-initramfs.py --qemu /caminho/qemu-aarch64
python3 test-dtb.py --input /caminho/quest3-live.dtb --dtc /caminho/dtc

## Critérios para fechar a validação no hardware, após resolver o handoff
1. Novo kernel chega ao init; UDC esperado aparece a high-speed.
2. PC enumera CDC ECM e cria interface com o MAC host previsto.
3. Host com IP 10.42.0.1/24 alcança 10.42.0.2; shell USB acessível.
4. Logs sem falha de probe/CFI/IOMMU; nenhum disco foi montado pelo init.
Ainda pendentes: handoff CFI, DMA/SMMU/estado herdado e captura de log confiável.
Não executar estes scripts como /init no Android stock nem aplicar DTB ao vivo.
