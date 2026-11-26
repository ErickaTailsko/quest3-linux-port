# Snapshot de pesquisa Quest 3

Fontes, ferramentas, testes e documentação do porte mínimo em RAM; diagnósticos
brutos incluídos no repositório mediante autorização expressa. Os assets
preservam os pacotes entregues ao longo da investigação, com checksums em
manifests/release-assets-local.json.

Não é uma release operacional. O kernel candidato não foi iniciado no Quest3,
o salto CFI permanece bloqueado e a captura confiável dos logs finais não foi
validada. O teste WARM foi atravessado por resets adicionais do Singularity;
o resultado não isola a retenção desse primeiro reset.

`quest3-native-kexec-experimental.tar.gz` é um experimento histórico com
divergências de configuração. Não substituir o candidato RAM-first por ele.
Pacotes `*-fix` são versões históricas, não patches a aplicar todos em sequência.
Consultar o checklist/STATUS atuais antes de qualquer ação no aparelho.

Esta publicação não instala autorun, não faz flash e não inicia testes físicos.
