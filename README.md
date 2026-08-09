# SYS CREDIÁRIO

Sistema de controle de crediário para Windows. Aplicativo com janela própria,
funciona **100% offline**, guarda os dados no próprio computador da empresa e
não depende de navegador.

- Cadastro de clientes (nome, CPF e telefone — nada além disso)
- Crediários com geração automática das parcelas
- Situação da parcela calculada sozinha: **PAGO**, **EM ABERTO**, **ATRASADO**
- Registro de pagamento com identificador da operação
- **Comprovante de pagamento em PDF** (A4 ou compacto), pronto para imprimir
- Estorno auditado: o pagamento nunca é apagado, e o motivo fica registrado
- Tela de atrasados, recebimentos, relatórios e backup
- Verificação do banco de dados sem reparo automático
- Cobrança amigável pelo WhatsApp (o envio é sempre decisão do funcionário)
- Login com perfis de Administrador e Funcionário, cada um com sua tela inicial
- Acesso opcional pelo celular na rede local (Wi‑Fi da empresa)

---

## Passo 1 — Instalar o Python

1. Acesse <https://www.python.org/downloads/windows/>
2. Baixe o **Python 3.11** ou superior.
3. Na primeira tela do instalador, **marque a caixa "Add Python to PATH"**.
4. Clique em *Install Now* e aguarde.

Para conferir, abra o **Prompt de Comando** e digite:

```bat
python --version
```

Deve aparecer algo como `Python 3.12.x`.

---

## Passo 2 — Instalar as dependências

Coloque a pasta `SYS_Crediario` em um local fácil, por exemplo `C:\SYS_Crediario`.
Depois, no Prompt de Comando:

```bat
cd C:\SYS_Crediario
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## Passo 3 — Executar o sistema

```bat
cd C:\SYS_Crediario
python main.py
```

A janela do **SYS CREDIÁRIO** abre em seguida.

---

## Passo 4 — Criar o usuário administrador

No **primeiro uso**, a própria tela de entrada pede a criação do dono do sistema:

1. Preencha **nome completo**, **usuário** e **senha** (mínimo 6 caracteres).
2. Confirme a senha e clique em **Criar administrador e entrar**.

A senha nunca é guardada em texto puro — é protegida com Argon2 (ou bcrypt).

Depois, em **CONFIGURAÇÕES → Usuários**, o administrador cadastra os funcionários.

| Ação | Administrador | Funcionário |
|------|:---:|:---:|
| Cadastrar e editar cliente | ✔ | ✔ |
| Criar crediário | ✔ | ✔ |
| Registrar pagamento | ✔ | ✔ |
| Emitir comprovante | ✔ | ✔ |
| Abrir WhatsApp | ✔ | ✔ |
| Estornar pagamento | ✔ | — |
| Excluir cliente | ✔ | — |
| Ver atrasados e relatórios | ✔ | — |
| Restaurar backup | ✔ | — |
| Verificar banco de dados | ✔ | — |
| Gerenciar usuários e ver logs | ✔ | — |

As regras são conferidas **nos serviços**, não apenas na interface: o funcionário
não contorna nenhuma delas nem chamando o código direto ou pela API do celular.
Ele também não vê os menus administrativos — a tela inicial dele é um terminal
com quatro ações grandes (**Novo cliente**, **Registrar pagamento**, **Pesquisar
cliente**, **Comprovantes**) e atalhos `Ctrl+N`, `Ctrl+R`, `Ctrl+F` e `Ctrl+P`.

---

## Passo 5 — Cadastrar o primeiro cliente

1. Menu lateral → **CLIENTES**
2. Botão **Novo cliente**
3. Preencha:
   - **Nome completo**
   - **CPF** (a máscara `000.000.000-00` é aplicada sozinha e o CPF é validado)
   - **Telefone** (máscara `(00) 00000-0000`)
4. **Salvar cliente**

O CPF é único: se já existir, o sistema avisa e não deixa duplicar.
Na busca, digite nome, CPF ou telefone — apertando **Enter** sobre um CPF já
cadastrado a ficha financeira abre direto.

---

## Passo 6 — Criar o primeiro crediário

1. Menu lateral → **NOVO CREDIÁRIO**
2. Selecione o cliente
3. Informe:
   - **Valor total da compra** — ex.: `1200,00`
   - **Entrada** — ex.: `200,00`
   - Os valores aceitam as formas usadas no dia a dia: `1200,00`, `1.200,00`,
     `1.200` e `1200`. Digitar `1.500` cadastra mil e quinhentos reais.
   - **Quantidade de parcelas** — ex.: `5`
   - **Data do primeiro vencimento**
4. A simulação aparece na hora:
   `Valor financiado: R$ 1.000,00 • 5x de R$ 200,00`
5. **Criar crediário**

As parcelas e os vencimentos mês a mês são gerados automaticamente. Quando a
divisão gera diferença de centavos, o ajuste vai para a **última parcela**, de
modo que a soma feche exatamente com o valor financiado.

---

## Passo 7 — Registrar um pagamento

1. Abra o crediário (em **CREDIÁRIOS**, na ficha do cliente ou pelo painel)
2. Clique na parcela desejada
3. Botão **Marcar como pago**

Na mesma hora o sistema atualiza saldo do cliente, saldo do crediário, painel,
relatórios, recebimentos e retira a parcela da lista de atrasados.

### Comprovante

Em **RECEBIMENTOS**, selecione o pagamento e clique em **Comprovante**
(ou dê dois cliques na linha, ou use `Ctrl+P`). Escolha o formato:

- **A4** — folha inteira, para o arquivo da empresa.
- **COMPACTO** — 80 mm de largura, para impressora térmica de balcão.

O PDF é gerado offline e o sistema oferece abrir o arquivo para impressão. Ele
traz nome do cliente, **CPF parcialmente mascarado** (`529.***.**7-25`), parcela,
valor, data, hora, identificador da operação, funcionário responsável, a situação
*PAGO* e espaço para assinatura da empresa. Os arquivos ficam em
`SYS_Crediario\comprovantes\`.

### Estorno

Se o pagamento foi lançado por engano, o administrador usa **Estornar
pagamento** e **informa o motivo**, que é obrigatório.

O recebimento **não é apagado**: ele sai do caixa e continua no histórico
marcado como estornado, junto com motivo, autor, data e hora. A parcela volta
para *EM ABERTO* ou *ATRASADO* conforme o vencimento e pode ser paga de novo.

---

## Passo 8 — Gerar o executável (.exe)

Com as dependências já instaladas, dê **dois cliques** em:

```
build_exe.bat
```

Ao final, o programa fica em:

```
C:\SYS_Crediario\dist\SYS_Crediario.exe
```

O executável abre direto na interface, sem janela preta de terminal.
Para colocar um ícone na Área de Trabalho, dê dois cliques em `criar_atalho.bat`.

---

## Onde ficam os dados

```
C:\Users\SEU_USUARIO\SYS_Crediario\
├── data\sys_crediario.db     banco de dados
├── backups\                  backups gerados
├── comprovantes\             comprovantes de pagamento em PDF
└── logs\                     registro técnico (rotativo, até 5 arquivos de 2 MB)
```

Essa pasta é **permanente**: atualizar o programa ou trocar o `.exe` não apaga
nada. Faça backup dela regularmente.

---

## Backup

Menu lateral → **BACKUP**

- **Criar backup** — gera um arquivo como `SYS_Crediario_Backup_2026-08-08_2030.db`
  no local que você escolher (pen drive, nuvem, rede).
- **Restaurar backup** — o sistema confere se o arquivo é mesmo um banco do
  SYS CREDIÁRIO, pede confirmação e **guarda automaticamente uma cópia dos dados
  atuais** antes de substituir. Backups de versões anteriores são migrados
  automaticamente depois de restaurados.
- **Verificar banco de dados** — roda a verificação de integridade e de vínculos
  do SQLite. É só diagnóstico: **nenhum reparo automático é tentado**, porque um
  reparo malfeito destrói dados. Se algo aparecer, o caminho seguro é restaurar o
  último backup bom.

---

## Acesso pelo celular (rede local)

Menu lateral → **CONFIGURAÇÕES → Acesso pelo celular → Ativar**.

O computador passa a exibir algo como:

```
SYS Mobile disponível na rede local.
Endereço: http://192.168.0.15:8765 • Porta: 8765
```

No celular, conectado ao **mesmo Wi‑Fi**, abra esse endereço. A documentação das
operações fica em `http://SEU_IP:8765/docs`.

O celular nunca acessa o arquivo do banco: tudo passa por uma API com login e
token. Consultas disponíveis: clientes, saldo, crediários, parcelas, atrasados,
painel e registro de pagamento para quem tem permissão.

**Celular perdido ou roubado:** encerrar a sessão (`POST /auth/logout`) invalida
o token na hora, e ele deixa de funcionar. Desligar o **Acesso pelo celular** nas
configurações derruba todos os aparelhos de uma vez.

> Se o Windows perguntar sobre o firewall, autorize o acesso em **redes privadas**.

---

## WhatsApp

O botão **WhatsApp** monta a mensagem de cobrança com o nome do cliente, o valor
vencido e a data, e abre a conversa já preenchida. **O sistema nunca envia
sozinho** — o funcionário confere e decide.

Sem internet aparece o aviso *"Não foi possível abrir o WhatsApp. Verifique sua
conexão com a internet."*, e todo o restante do programa continua funcionando
normalmente.

---

## Testes

```bat
cd C:\SYS_Crediario
python -m pytest
```

Cobrem CPF válido/inválido/duplicado, cálculo de parcelas, diferença de
centavos, geração de datas, parcela atrasada, registro e estorno de pagamento,
cálculo de saldo, total vencido, permissões e backup.

Também cobrem a leitura de valores em reais (`1.500` = mil e quinhentos), a
recusa de dois recebimentos para a mesma parcela, a API do celular (token,
permissão do funcionário e encerramento de sessão) e a migração de bancos
criados por versões anteriores.

E ainda: o estorno auditado (pagamento preservado, motivo obrigatório, saída do
caixa e nova cobrança possível), o comprovante em PDF nos dois formatos com CPF
mascarado, o RBAC provado **chamando os serviços direto** — como faria um script
ou a API — e a interface por perfil (o funcionário não tem as telas
administrativas nem instanciadas).

Os mesmos testes rodam automaticamente no GitHub a cada envio de código
(aba **Actions**), em Python 3.11 e 3.12.

---

## Estrutura do projeto

```
SYS_Crediario/
├── main.py                 inicialização do aplicativo
├── requirements.txt
├── build_exe.bat           gera o SYS_Crediario.exe
├── criar_atalho.bat        atalho na Área de Trabalho
├── app/
│   ├── config.py           caminhos, versão e URL do banco
│   ├── database/           conexão, tipos monetários e migrações
│   ├── models/             tabelas (usuários, clientes, crediários, parcelas,
│   │                       pagamentos, logs, configurações)
│   ├── repositories/       consultas ao banco
│   ├── services/           regras de negócio
│   ├── security/           senhas, sessão e permissões
│   ├── ui/                 telas em PySide6
│   ├── api/                servidor local FastAPI
│   └── utils/              CPF, dinheiro, datas, validação, WhatsApp, exportação
├── tests/                  testes automatizados
└── site/                   páginas do site do autor (não faz parte do programa)
```

---

## Evolução para servidor (PostgreSQL)

A separação entre banco, regras, API e interface já está pronta. Para migrar,
basta definir uma variável de ambiente antes de abrir o programa:

```bat
set SYS_DATABASE_URL=postgresql+psycopg://usuario:senha@servidor:5432/sys_crediario
python main.py
```

Nenhuma linha de regra de negócio precisa mudar.

---

## Segurança e LGPD

- Coleta mínima: apenas nome, CPF e telefone.
- Senhas com hash forte; nunca em texto puro.
- Todo acesso ao banco passa por ORM com parâmetros — sem SQL Injection.
- Permissões por papel e registro de auditoria das ações sensíveis.
- Após **5 senhas erradas seguidas**, o usuário fica bloqueado por **10 minutos**.
  O bloqueio se desfaz sozinho e uma senha correta zera a contagem. Para ajustar:
  `SYS_LOGIN_MAX_ATTEMPTS` e `SYS_LOGIN_LOCK_MINUTES`.
- Uma parcela aceita **um único recebimento**, garantido pelo próprio banco: o
  caixa não conta o mesmo pagamento duas vezes se o balcão e o celular
  registrarem a mesma parcela ao mesmo tempo.
- Cliente com histórico financeiro não pode ser excluído; a exclusão
  administrativa exige confirmação do CPF.
- Pagamento nunca é apagado: o estorno é exclusão lógica, com motivo obrigatório,
  autor, data e hora, e o recebimento original fica no histórico.
- Todo pagamento recebe um identificador (`PAG-20260809-0001`) que aparece no
  comprovante e na auditoria.
- O comprovante sai com o CPF parcialmente mascarado.
