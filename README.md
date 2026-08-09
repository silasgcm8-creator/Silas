# SYS CREDIÁRIO

Sistema de controle de crediário para Windows. Aplicativo com janela própria,
funciona **100% offline**, guarda os dados no próprio computador da empresa e
não depende de navegador.

- Cadastro de clientes (nome, CPF e telefone — nada além disso)
- Crediários com geração automática das parcelas
- Situação da parcela calculada sozinha: **PAGO**, **EM ABERTO**, **ATRASADO**
- Registro de pagamento com identificador da operação
- **Comprovante de pagamento em PDF** (A4 ou compacto), pronto para imprimir
- **Módulo BOLETOS**: documentos de cobrança por parcela, em três modalidades,
  com histórico, filtros, reimpressão, cancelamento e recebimento no caixa
- **Carnê de pagamento** com todas as parcelas, QR Code Pix da loja e área
  reservada para o código de barras do banco
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
| Emitir carnê / Pix | ✔ | ✔ |
| Criar cobrança, imprimir e reimprimir | ✔ | ✔ |
| Receber pagamento e imprimir comprovante | ✔ | ✔ |
| Cancelar documento de cobrança | ✔ | — |
| Cadastrar / alterar contas bancárias | ✔ | — |
| Configurar modalidades de cobrança | ✔ | — |
| Abrir WhatsApp | ✔ | ✔ |
| Estornar pagamento | ✔ | — |
| Excluir cliente | ✔ | — |
| Ver atrasados e relatórios | ✔ | — |
| Restaurar backup | ✔ | — |
| Verificar banco de dados | ✔ | — |
| Configurar empresa, Pix e backup | ✔ | — |
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

### Carnê de pagamento (parcelamento, Pix e código de barras)

Na ficha do crediário, botão **Carnê / Pix**. O PDF em A4 traz:

- cliente, CPF mascarado e telefone;
- valor total, entrada, valor financiado e quantidade de parcelas;
- **todas as parcelas** com número, vencimento, valor e situação
  (PAGO / EM ABERTO / ATRASADO com os dias de atraso);
- totais de pago, saldo devedor e valor vencido;
- **área do Pix** e **área do código de barras**.

O nome da empresa impresso nos documentos já vem como **VISÃO** e pode ser
alterado em **CONFIGURAÇÕES → Empresa e Pix**.

**Pix.** Cadastre a chave em **CONFIGURAÇÕES → Empresa e Pix**. Com ela, o carnê
sai com o QR Code e o *copia e cola* gerados pelo próprio sistema, no padrão
aberto do Banco Central, já com o saldo devedor. O dinheiro cai na conta da
empresa. Sem chave cadastrada, a área fica reservada em branco — o sistema
**nunca inventa dados bancários**.

**Código de barras.** A área é reservada para a empresa colar a linha digitável
emitida pelo banco dela. O sistema imprime nesse espaço apenas um código de
barras **de controle interno** (o número do documento), para conferência no
balcão.

> Este carnê **não é um boleto bancário**: apenas um banco pode emitir um título
> cobrável na rede bancária. O próprio documento diz isso no rodapé, para que
> ninguém o confunda com uma cobrança registrada.

---

## Módulo BOLETOS

Menu lateral → **BOLETOS**. É onde ficam todos os documentos de cobrança
emitidos, com filtros rápidos (**Todos / Em aberto / Pagos / Atrasados /
Cancelados**), busca por nome, CPF, número do documento, crediário ou parcela, e
filtro por tipo, conta e período (emissão ou vencimento).

Ações: **reimprimir / abrir PDF**, **receber pagamento**, **comprovante**,
**histórico** e **cancelar documento** (só administrador).

### Três modalidades

| | O que sai impresso |
|---|---|
| **Exclusivamente na Ótica Visão** | Pagamento presencial. **Nenhum** dado bancário no documento. |
| **Banco / PIX** | Os dados da conta que o administrador cadastrou, incluindo a chave Pix. |
| **Boleto bancário registrado** | Só com integração oficial contratada com o banco. |

> O sistema **nunca cria** linha digitável, código de barras bancário, nosso
> número ou dado bancário fictício. Sem integração oficial, a emissão de boleto
> registrado é recusada com mensagem clara. Os dados de banco só existem porque
> o administrador os digitou.

### Criando uma cobrança

Na ficha do crediário → selecione a parcela → **Documento de cobrança**.
Escolha o tipo de pagamento; a tela mostra apenas o que interessa àquela
modalidade. Pode informar **juros/multa** e **desconto**, e o documento traz
valor original, ajustes e **valor atualizado**.

O documento sai em A4 com **VALOR A PAGAR** e **VENCIMENTO** em destaque, e um
**comprovante destacável** no rodapé, com espaço para data, forma de pagamento e
assinatura. O arquivo é nomeado
`Cobranca_NomeCliente_Parcela_XX_DD-MM-AAAA.pdf`, já com os caracteres inválidos
do Windows removidos.

Cada documento recebe um número interno (**OV-000001**) e um **QR Code
interno**, que carrega só esse número — nada de CPF, telefone ou nome dentro do
QR. Ele serve para localizar a cobrança: digite ou leia o número na busca de
**Clientes** e o crediário abre direto. **O QR não é Pix e não é boleto.**

### Recebendo o pagamento

Em **BOLETOS** → selecione o documento → **Receber pagamento**. Escolha a forma
realmente usada no caixa (dinheiro, PIX, débito, crédito, transferência, outro)
— mesmo que o documento tenha sido emitido para pagamento presencial. O sistema
pede **confirmação** com cliente, parcela, valor e forma antes de baixar a
parcela, e só então marca como **PAGO**. Em seguida oferece o comprovante.

A situação do documento acompanha a parcela: **EM ABERTO**, **PAGO**,
**ATRASADO**. **CANCELADO** é o único estado gravado, com autor e motivo.
Uma parcela só pode ter **um documento ativo**; cancelar libera nova emissão.

### Contas de recebimento

**CONFIGURAÇÕES → Bancos e recebimentos** (somente administrador): nome de
identificação, banco e código, agência e dígito, conta e dígito, tipo de conta,
beneficiário, CPF/CNPJ, chave Pix e tipo, além de carteira, convênio e código do
beneficiário para uso futuro em cobrança registrada. Pode cadastrar várias
contas ("Banco Principal", "PIX Loja") e desativar as que não usa mais.
Conta já usada em cobrança é **desativada em vez de apagada**, para não destruir
a informação de documentos emitidos.

**CONFIGURAÇÕES → Cobranças**: quais modalidades ficam liberadas e qual é a
padrão (ou *perguntar sempre*).

### Estorno

Se o pagamento foi lançado por engano, o administrador usa **Estornar
pagamento** e **informa o motivo**, que é obrigatório.

O recebimento **não é apagado**: ele sai do caixa e continua no histórico
marcado como estornado, junto com motivo, autor, data e hora. A parcela volta
para *EM ABERTO* ou *ATRASADO* conforme o vencimento e pode ser paga de novo.

---

## Passo 8 — Gerar o executável (.exe)

Com o Python instalado, dê **dois cliques** em:

```
build_exe.bat
```

O script cuida de tudo: cria um ambiente isolado (`.venv`), instala as
dependências, compila com o PyInstaller e — o mais importante — **verifica o
executável no final**. Se algo faltar no empacotamento, ele avisa em vez de
entregar um programa que quebra no balcão.

Ao terminar, o programa fica em:

```
C:\SYS_Crediario\dist\SYS_Crediario.exe
```

Um único arquivo, com ícone próprio, que abre direto na interface — sem janela
preta de terminal e sem precisar de Python instalado na máquina que vai usar.

Depois, dois cliques em `criar_atalho.bat` para colocar o ícone na Área de
Trabalho.

### Verificar a instalação

A qualquer momento, dois cliques em:

```
verificar.bat
```

Ele confere, em poucos segundos, tudo que depende de biblioteca externa: banco
de dados, senhas, interface, geração de PDF, **QR Code e código de barras**,
leitura do logotipo, servidor do celular, exportações, e emite de verdade um
comprovante, um carnê e um documento de cobrança.

```
[OK  ] Banco de dados e migrações
[OK  ] Senhas (Argon2 / bcrypt) — algoritmo argon2id
[OK  ] Interface e ícones (PySide6) — PySide6 6.7.2
[OK  ] PDF, QR Code e código de barras — com QR e código de barras
[OK  ] Documentos do sistema — cobrança, carnê e comprovante gerados
  Tudo certo. O sistema está pronto para uso.
```

A verificação roda em uma **área temporária**: não toca no banco da loja e não
deixa usuário nenhum para trás. O relatório também é gravado em
`SYS_Crediario\logs\verificacao.txt`.

> **Se a verificação falhar**, não use o executável no atendimento — mande o
> arquivo `verificacao.txt` para quem cuida do sistema. A lista diz exatamente
> qual parte não funcionou.

### Detalhes do empacotamento

A receita fica em `SYS_Crediario.spec`, versionada junto com o código. Ela
declara o que o PyInstaller **não descobre sozinho**: o `uvicorn` escolhe
protocolo por nome em tempo de execução, e o `reportlab` monta os widgets de
código de barras executando uma string com o nome do módulo — sem coletar o
pacote inteiro, o executável falharia em **todo PDF com QR**, ou seja, no
documento de cobrança e no carnê. Esse caso já aconteceu e hoje tem teste
guardando.

## Onde ficam os dados

```
C:\Users\SEU_USUARIO\SYS_Crediario\
├── data\sys_crediario.db     banco de dados
├── backups\                  backups gerados
├── comprovantes\             comprovantes, carnês e cobranças em PDF
└── logs\                     registro técnico (rotativo) e verificacao.txt
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
- **Backup automático** — em **CONFIGURAÇÕES → Backup automático** você liga,
  escolhe o intervalo em horas, a pasta (pen drive, nuvem, rede) e quantas
  cópias manter. A cópia é feita quando o programa abre, se o intervalo venceu.
  Pen drive removido não impede o sistema de abrir: o erro vai para o log.
  A limpeza automática só apaga arquivos `_Auto_` — backup manual e cópia de
  pré-restauração nunca são removidos.
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

E ainda: o carnê com Pix (inclusive o CRC do padrão do Banco Central conferido
contra o valor de verificação oficial), a exclusão lógica de cliente com
reativação, o backup automático com retenção, a paginação de base grande,
o estorno auditado (pagamento preservado, motivo obrigatório, saída do
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
├── build_exe.bat           gera o SYS_Crediario.exe e verifica no final
├── criar_atalho.bat        atalho na Área de Trabalho
├── verificar.bat           confere a instalação nesta máquina
├── SYS_Crediario.spec      receita do empacotamento (revisável)
├── assets/icone.ico        ícone do executável
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
│   ├── services/banking/   camada de integração bancária (futuro)
│   └── utils/              CPF, dinheiro, datas, validação, WhatsApp, Pix,
│                           exportação
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
