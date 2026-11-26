# USB trim2 — build concluído, ainda sem destino elegível

**Image-only terminou com retorno zero e passou no verificador ampliado.**
Não houve nova operação ADB, aquisição de memória, envio de payload ou boot.

## Comparação

| Candidato | image_size | Arquivo Image |
|---|---:|---:|
| QMP | 43,125 MiB | 43.565.568 bytes |
| USB trim1 | 39,125 MiB | 39.418.368 bytes |
| USB trim2 | **35,9375 MiB** | 36.067.840 bytes |

Trim2 reduziu 3,1875 MiB frente ao trim1; redução total de 7,1875 MiB
(16,6667%) frente ao QMP. O image_size efetivo é 37.683.200 bytes. Faltariam
11,9375 MiB para igualar o trecho MOVABLE histórico de 24 MiB. Esse trecho
não é propriedade do loader e não foi revalidado neste build.

Release: `5.10.246-gd7102a837402-q3-usb-trim2`.
SHA-256 Image: `854bb03652d2f0345878361eb103d597c4edfd4d86fbc4bf6a58a26dee0d6578`.
SHA-256 config: `5bdae0670303ed5fa7dbe1bce6bf145279abba5c6fee0e1c63f3584cceb927c1`.

llvm-size mediu text/readonly 24.808.821 bytes, data 11.048.116 e bss
1.544.416. Essas classes e o tamanho do arquivo não substituem image_size.

## Artefatos conferidos

- Release trim2 e raízes de subsistemas removidos não reativadas.
- Provedores QMP embutidos, config/flags registradas de CFI/SCS/LTO/x18,
  IPCC/GIC e requisitos de initramfs gzip/ELF/scripts/TTY/RAM filesystems.
- Símbolos QMP, cabeçalho ELF64 ARM64 e vmlinux.symvers.
- Checagem geométrica contra a amostra histórica; nenhum run comporta o Image.

Não houve compilação do conjunto completo de módulos ou comprovação de ABI
de módulos stock. As dependências hardware não foram validadas pelo build.
Mantidos os diagnósticos const de modpost e duas consultas Git sem revisão
ancestral no checkout raso. Make terminou zero; o log não foi ocultado ou
declarado livre de avisos. O emissor exato da consulta Git segue não identificado.

Metadados públicos em `quest3/usb-trim/trim2-verification.json`,
`trim2-geometry.json` e `trim2-comparison.json`. Cópia local do Image/config,
mapas e log em `private-diagnostics/usb-trim2-artifacts/`, com manifesto próprio.
Os candidatos anteriores permanecem separados.

## Plano relativo, não um payload pronto

Mantendo slots de 2 MiB para initramfs e DT: slot Image de 36 MiB,
initrd relativo em 0x2400000, DT em 0x2600000; janela total de **40 MiB**.
Nenhuma base física foi escolhida, nenhum DT novo foi gerado para esses
offsets e nenhum suporte dinâmico foi implementado no loader.

O campo image_entry do verificador descreve o contrato fixo anterior, não
autoriza sobrescrever 0x90000000. O plano não prova reservas, validade de todos
os PFNs, posse, initrd window ARM64, DMA ou estado herdado de dispositivos.

## Próxima decisão

Já há duas reduções medidas e ambas continuam maiores que o trecho observado.
Não reduzir provedores ou proteções às cegas só para atingir 24 MiB. Revisar
uma estratégia de destino adquirível (ou justificar novos cortes a partir de
medição), antes de outro build ou amostra no aparelho. Qualquer ampliação de
sondagem com pausa global precisa de plano e autorização próprios.

Captura inicial de logs, handoff CFI, CPUs e DMA continuam bloqueios independentes.
