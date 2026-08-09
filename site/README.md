<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Nicolau Ranvier – Livros</title>
  <meta name="description" content="Site oficial do autor Nicolau Ranvier. Conheça e compre seus livros em versão digital e impressa.">

  <style>
    :root {
      --bg: #f5f5f7;
      --card: #ffffff;
      --text: #111827;
      --muted: #6b7280;
      --accent: #f97316;
      --accent-soft: #ffedd5;
      --border: #e5e7eb;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
    }

    a {
      color: inherit;
      text-decoration: none;
    }

    header {
      position: sticky;
      top: 0;
      z-index: 10;
      background: rgba(245, 245, 247, 0.96);
      border-bottom: 1px solid var(--border);
      backdrop-filter: blur(8px);
    }

    .nav {
      max-width: 960px;
      margin: 0 auto;
      padding: 0.9rem 1rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 0.95rem;
    }

    .logo {
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .logo span {
      color: var(--accent);
    }

    .nav-links {
      display: flex;
      gap: 1.1rem;
      font-size: 0.9rem;
    }

    .nav-links a {
      position: relative;
      padding-bottom: 0.15rem;
    }

    .nav-links a::after {
      content: "";
      position: absolute;
      left: 0;
      bottom: 0;
      width: 0;
      height: 2px;
      background: var(--accent);
      transition: width 0.15s;
    }

    .nav-links a:hover::after {
      width: 100%;
    }

    main {
      max-width: 960px;
      margin: 0 auto;
      padding: 1.5rem 1rem 3rem;
    }

    /* HERO */
    .hero {
      display: grid;
      grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
      gap: 1.75rem;
      align-items: center;
      padding: 1.5rem 0 2.25rem;
    }

    .hero-badge {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      background: var(--accent-soft);
      color: var(--accent);
      padding: 0.25rem 0.7rem;
      border-radius: 999px;
      font-size: 0.8rem;
      margin-bottom: 0.8rem;
    }

    .hero h1 {
      font-size: clamp(1.9rem, 3vw, 2.5rem);
      margin-bottom: 0.6rem;
    }

    .hero p {
      font-size: 0.95rem;
      color: var(--muted);
      margin-bottom: 1.1rem;
    }

    .hero-buttons {
      display: flex;
      flex-wrap: wrap;
      gap: 0.6rem;
      margin-bottom: 0.6rem;
    }

    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 0.7rem 1.2rem;
      border-radius: 999px;
      border: 1px solid transparent;
      font-size: 0.9rem;
      font-weight: 600;
      cursor: pointer;
      transition: transform 0.1s, box-shadow 0.1s, background 0.1s, border-color 0.1s;
    }

    .btn-primary {
      background: var(--accent);
      color: #fff;
      box-shadow: 0 8px 18px rgba(0, 0, 0, 0.15);
    }

    .btn-primary:hover {
      transform: translateY(-1px);
      box-shadow: 0 12px 24px rgba(0, 0, 0, 0.18);
    }

    .btn-ghost {
      background: #fff;
      border-color: var(--border);
      color: var(--text);
    }

    .hero-note {
      font-size: 0.8rem;
      color: var(--muted);
    }

    .hero-card {
      background: linear-gradient(145deg, #fee2e2, #fef3c7, #e5e7eb);
      border-radius: 1.2rem;
      padding: 1.1rem;
      box-shadow: 0 16px 32px rgba(15, 23, 42, 0.25);
    }

    .hero-card-inner {
      background: rgba(255, 255, 255, 0.9);
      border-radius: 0.9rem;
      padding: 1rem;
      border: 1px solid rgba(15, 23, 42, 0.08);
    }

    .hero-book-tag {
      font-size: 0.7rem;
      text-transform: uppercase;
      letter-spacing: 0.09em;
      color: var(--accent);
      margin-bottom: 0.4rem;
    }

    .hero-book-title {
      font-weight: 700;
      margin-bottom: 0.3rem;
    }

    .hero-book-sub {
      font-size: 0.8rem;
      color: var(--muted);
      margin-bottom: 0.8rem;
    }

    .hero-book-meta {
      font-size: 0.8rem;
      color: var(--muted);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    /* Sections */
    section {
      padding: 1.8rem 0;
      border-top: 1px solid var(--border);
    }

    h2.section-title {
      font-size: 1.4rem;
      margin-bottom: 0.4rem;
    }

    p.section-subtitle {
      font-size: 0.9rem;
      color: var(--muted);
      margin-bottom: 1.3rem;
    }

    /* Sobre */
    .about {
      display: grid;
      grid-template-columns: minmax(0, 2fr) minmax(0, 1.4fr);
      gap: 1.6rem;
      align-items: center;
    }

    .about p + p {
      margin-top: 0.6rem;
    }

    .about-note {
      margin-top: 0.8rem;
      font-size: 0.85rem;
      color: var(--muted);
      padding: 0.7rem 0.8rem;
      border-radius: 0.7rem;
      background: #fff;
      border: 1px solid var(--border);
    }

    .author-avatar {
      width: 180px;
      height: 180px;
      border-radius: 50%;
      background: linear-gradient(135deg, #bfdbfe, #fed7aa);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 2.4rem;
      color: #111827;
      margin: 0 auto;
      border: 4px solid #e5e7eb;
    }

    /* Livros */
    .books-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 1rem;
    }

    .book-card {
      background: var(--card);
      border-radius: 0.9rem;
      padding: 1rem;
      border: 1px solid var(--border);
      box-shadow: 0 6px 14px rgba(15, 23, 42, 0.06);
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      font-size: 0.9rem;
    }

    .book-tag {
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--accent);
    }

    .book-title {
      font-weight: 600;
    }

    .book-desc {
      font-size: 0.85rem;
      color: var(--muted);
      flex: 1;
    }

    .book-meta {
      font-size: 0.8rem;
      color: var(--muted);
    }

    .book-actions {
      margin-top: 0.4rem;
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
    }

    .btn-outline {
      padding: 0.5rem 0.9rem;
      border-radius: 999px;
      border: 1px solid var(--accent);
      font-size: 0.8rem;
      font-weight: 500;
      background: transparent;
      cursor: pointer;
      transition: background 0.1s, color 0.1s;
    }

    .btn-outline:hover {
      background: var(--accent);
      color: #fff;
    }

    /* Contato */
    .contact-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.4fr) minmax(0, 1.6fr);
      gap: 1.3rem;
      align-items: flex-start;
    }

    .contact-card {
      background: var(--card);
      border-radius: 0.9rem;
      padding: 1rem;
      border: 1px solid var(--border);
      font-size: 0.9rem;
    }

    .contact-item + .contact-item {
      margin-top: 0.4rem;
    }

    .contact-label {
      font-weight: 600;
    }

    .contact-form {
      display: grid;
      gap: 0.6rem;
      margin-top: 0.4rem;
    }

    .contact-form label {
      font-size: 0.8rem;
      font-weight: 500;
    }

    .contact-form input,
    .contact-form textarea {
      width: 100%;
      padding: 0.5rem 0.6rem;
      border-radius: 0.5rem;
      border: 1px solid var(--border);
      font-family: inherit;
      font-size: 0.9rem;
    }

    .contact-form textarea {
      min-height: 80px;
      resize: vertical;
    }

    footer {
      border-top: 1px solid var(--border);
      padding: 1rem;
      text-align: center;
      font-size: 0.8rem;
      color: var(--muted);
      background: #f9fafb;
    }

    @media (max-width: 860px) {
      .hero {
        grid-template-columns: minmax(0, 1fr);
      }

      .hero-card {
        order: -1;
      }

      .about {
        grid-template-columns: minmax(0, 1fr);
      }

      .books-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .contact-grid {
        grid-template-columns: minmax(0, 1fr);
      }
    }

    @media (max-width: 640px) {
      .nav-links {
        display: none;
      }

      main {
        padding-inline: 0.8rem;
      }

      .books-grid {
        grid-template-columns: minmax(0, 1fr);
      }
    }
  </style>
</head>
<body>

<header>
  <div class="nav">
    <div class="logo">
      NICOLAU <span>RANVIER</span>
    </div>
    <nav class="nav-links">
      <a href="#livros">Livros</a>
      <a href="#sobre">Sobre</a>
      <a href="#contato">Contato</a>
    </nav>
  </div>
</header>

<main>
  <!-- HERO -->
  <section class="hero">
    <div>
      <div class="hero-badge">
        📚 Site oficial de Nicolau Ranvier
      </div>
      <h1>Histórias que falam direto com o leitor.</h1>
      <p>
        Livros escritos para quem gosta de emoção, reflexão e personagens que parecem reais.
        Compre diretamente com o autor em versão digital ou impressa.
      </p>
      <div class="hero-buttons">
        <a href="#livros" class="btn btn-primary">Ver livros disponíveis</a>
        <!-- TROQUE ESTE LINK PELA SUA PÁGINA NA AMAZON -->
        <a href="#" class="btn btn-ghost">Comprar na Amazon</a>
      </div>
      <div class="hero-note">
        Envio para todo o Brasil · E-books com acesso imediato após a compra.
      </div>
    </div>

    <div class="hero-card">
      <div class="hero-card-inner">
        <div class="hero-book-tag">Livro em destaque</div>
        <div class="hero-book-title">Título do Livro Principal</div>
        <div class="hero-book-sub">
          Uma história sobre escolhas, perdão e recomeços.
        </div>
        <div class="hero-book-meta">
          <span>~ 220 páginas</span>
          <span>E-book e físico</span>
        </div>
      </div>
    </div>
  </section>

  <!-- SOBRE -->
  <section id="sobre">
    <h2 class="section-title">Sobre o autor</h2>
    <p class="section-subtitle">
      Quem é Nicolau Ranvier e o que inspira seus livros.
    </p>

    <div class="about">
      <div>
        <p>
          Nicolau Ranvier é um autor brasileiro que escreve para quem gosta de histórias
          que misturam emoção, verdade e reflexão. Em seus livros, o foco está sempre nas
          relações humanas, nas decisões difíceis e na possibilidade de recomeçar.
        </p>
        <p>
          Com uma linguagem acessível e direta, ele busca criar uma leitura envolvente,
          daquelas que fazem o leitor pensar na própria vida e nas pessoas ao redor.
        </p>
        <div class="about-note">
          ✍️ Disponível para parcerias, clubes de leitura, entrevistas e eventos literários.
        </div>
      </div>
      <div>
        <!-- Se tiver foto, troque por <img src="URL_DA_FOTO" alt="Foto de Nicolau Ranvier" class="author-avatar-img"> -->
        <div class="author-avatar">NR</div>
      </div>
    </div>
  </section>

  <!-- LIVROS -->
  <section id="livros">
    <h2 class="section-title">Livros de Nicolau Ranvier</h2>
    <p class="section-subtitle">
      Clique no livro para ver detalhes e opções de compra.
    </p>

    <div class="books-grid">
      <!-- LIVRO 1 -->
      <article class="book-card">
        <div class="book-tag">Romance</div>
        <div class="book-title">Título do Livro 1</div>
        <div class="book-desc">
          Uma breve sinopse do livro 1. Fale em poucas linhas sobre o personagem principal,
          o conflito e o clima da história, para despertar curiosidade.
        </div>
        <div class="book-meta">
          ~ 220 páginas · E-book e físico
        </div>
        <div class="book-actions">
          <!-- TROCAR # PELO LINK DE COMPRA -->
          <a href="#" class="btn-outline">Comprar e-book</a>
          <a href="#" class="btn-outline">Comprar físico</a>
        </div>
      </article>

      <!-- LIVRO 2 -->
      <article class="book-card">
        <div class="book-tag">Ficção contemporânea</div>
        <div class="book-title">Título do Livro 2</div>
        <div class="book-desc">
          Descrição rápida do livro 2. Explique o tema principal e por que esse livro
          é ideal para certo tipo de leitor.
        </div>
        <div class="book-meta">
          ~ 180 páginas · E-book
        </div>
        <div class="book-actions">
          <a href="#" class="btn-outline">Comprar e-book</a>
        </div>
      </article>

      <!-- LIVRO 3 -->
      <article class="book-card">
        <div class="book-tag">Não-ficção</div>
        <div class="book-title">Título do Livro 3</div>
        <div class="book-desc">
          Se este for um livro de desenvolvimento pessoal, espiritualidade ou outro tema,
          explique como ele pode ajudar o leitor de forma prática.
        </div>
        <div class="book-meta">
          ~ 150 páginas · E-book e físico sob demanda
        </div>
        <div class="book-actions">
          <a href="#" class="btn-outline">Ver mais detalhes</a>
        </div>
      </article>
    </div>
  </section>

  <!-- CONTATO -->
  <section id="contato">
    <h2 class="section-title">Contato</h2>
    <p class="section-subtitle">
      Fale diretamente com o autor para dúvidas, parcerias e convites.
    </p>

    <div class="contact-grid">
      <div class="contact-card">
        <div class="contact-item">
          <span class="contact-label">E-mail: </span>
          <!-- TROQUE PELO SEU E-MAIL REAL -->
          <a href="mailto:seuemail@exemplo.com">seuemail@exemplo.com</a>
        </div>
        <div class="contact-item">
          <span class="contact-label">Instagram: </span>
          <!-- TROQUE PELO SEU @ REAL -->
          <a href="#" target="_blank">@seu_instagram</a>
        </div>
        <div class="contact-item">
          <span class="contact-label">Outras plataformas: </span>
          Amazon · Skoob · Goodreads
        </div>
        <p style="font-size: 0.8rem; color: var(--muted); margin-top: 0.6rem;">
          Normalmente respondo em até 2 dias úteis.
        </p>
      </div>

      <div class="contact-card">
        <p style="font-size: 0.9rem; margin-bottom: 0.6rem;">
          Este formulário é apenas visual. Para receber mensagens, use seu e-mail ou redes sociais
          enquanto não tiver um serviço de formulário configurado.
        </p>
        <form class="contact-form">
          <div>
            <label for="nome">Nome</label>
            <input id="nome" type="text" placeholder="Seu nome">
          </div>
          <div>
            <label for="email-contato">E-mail</label>
            <input id="email-contato" type="email" placeholder="seuemail@exemplo.com">
          </div>
          <div>
            <label for="mensagem">Mensagem</label>
            <textarea id="mensagem" placeholder="Escreva sua mensagem..."></textarea>
          </div>
          <button type="button" class="btn btn-primary">Enviar (exemplo)</button>
        </form>
      </div>
    </div>
  </section>
</main>

<footer>
  © <span id="ano"></span> Nicolau Ranvier · Todos os direitos reservados.
</footer>

<script>
  document.getElementById("ano").textContent = new Date().getFullYear();
</script>

</body>
</html>