# Quest 3: primeiro alvo em RAM — initramfs compilado

BusyBox 1.36.1 estático AArch64, glibc 2.41, GCC 14.2.0.
initramfs gzip/newc determinístico a partir do mesmo binário e init.
Build sem warnings no log final. Código-fonte oficial, COPYING e configuração
incluídos para reconstrução. crossroot/toolchain/emulador não distribuídos.

## Comportamento do init
Monta apenas proc, sysfs, devtmpfs, devpts, tmpfs, configfs e pstore.
Não monta armazenamento de bloco, não monta Android e não grava partições.
Configura USB ECM; exige exatamente um UDC. Sem controladora disponível, falha
com mensagem e espera, sem reiniciar automaticamente ou manipular watchdog.
Endereço do alvo: 10.42.0.2/24; configurar host direto como 10.42.0.1/24.
Sem DHCP, DNS, Wi-Fi, rota padrão ou userspace SteamOS.
Telnet de desenvolvimento sem autenticação, vinculado a 10.42.0.2:23;
usar exclusivamente conexão USB direta e isolada. /dev/pts necessário para PTY.
Snapshot dmesg fica em /tmp/kernel-at-init.log, só em RAM.

## Validação realizada
verify-initramfs.py: parser CPIO independente, nomes/modos/nós de dispositivo,
conteúdo byte a byte, ELF estático AArch64 sem PT_INTERP/PT_DYNAMIC, applets,
sintaxe do init e aritmética/testes do shell em QEMU user-mode, opções telnetd.
GNU cpio também listou o arquivo corretamente. Arquivo gerado novamente com
mesmo SHA256. Gerador recusou ELF inválido, host, dinâmico e saída existente.
QEMU user-mode NÃO inicializou o kernel, não executou o init como PID1 e não
validou controlador USB, rede, drivers ou hardware Quest.

## Pré-requisitos pendentes para boot
required.config lista as opções básicas. O kernel experimental existente ainda
não tem DEVTMPFS; seu DWC3_MSM é módulo, e este initramfs não carrega módulos.
É necessário resolver a cadeia USB/PHY/power/interconnect no kernel de destino
ou incluí-la em RAM e implementar carregamento. Não basta copiar este arquivo.

PSTORE/PSTORE_RAM/CONSOLE são requisitos de kernel; montar pstore não estabelece
retenção. Nenhuma região de RAM nova, endereço de staging ou writer privado foi
adicionado. Os testes de console e pmsg no aparelho não recuperaram marcadores.
Logo retained-log funcional permanece pendente, assim como handoff sob CFI,
shutdown/DMA e adaptação do DT/driver de core-hang. Não é imagem pronta de boot.
Este pacote não inclui Image, DTB, módulos do kernel nem comandos de reboot/flash.

## Reconstruir e verificar
Em Linux com cross GCC ARM64 e libc estática:
  CROSS_COMPILE=aarch64-linux-gnu- bash rebuild-busybox.sh NOVO_DIRETORIO
  python3 build.py --busybox NOVO_DIRETORIO/busybox-arm64 --out novo.cpio.gz
O BusyBox recompilado pode variar com versão do compilador/libc e build time;
não prometemos binário BusyBox idêntico entre toolchains diferentes.

Para conferir os artefatos distribuídos:
  sha256sum -c SHA256SUMS
  python3 verify-initramfs.py --qemu /caminho/qemu-aarch64
O verificador requer os nomes busybox-arm64, init e quest3-ram-first.cpio.gz
no mesmo diretório. verification.json registra os resultados.
