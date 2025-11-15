# Silas
Venda de livros
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nicolau Ranvier | Livros</title>
    <meta name="description" content="Site oficial de Nicolau Ranvier – conheça e compre seus livros.">
    
    <!-- Fonte do Google (opcional) -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap" rel="stylesheet">
    
    <style>
        :root {
            --bg: #f5f5f7;
            --primary: #1f2933;
            --accent: #f97316;
            --accent-soft: #ffedd5;
            --text: #111827;
            --muted: #6b7280;
            --card-bg: #ffffff;
            --border: #e5e7eb;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: "Poppins", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }

        a {
            text-decoration: none;
            color: inherit;
        }

        img {
            max-width: 100%;
            display: block;
        }

        /* Header / Navbar */
        header {
            position: sticky;
            top: 0;
            z-index: 50;
            background-color: rgba(245,245,247,0.96);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid var(--border);
        }

        .nav {
            max-width: 1100px;
            margin: 0 auto;
            padding: 1rem 1.5rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .logo {
            font-weight: 700;
            letter-spacing: 0.06em;
            font-size: 1.1rem;
            text-transform: uppercase;
        }

        .logo span {
            color: var(--accent);
        }

        .nav-links {
            display: flex;
            gap: 1.5rem;
            font-size: 0.95rem;
        }

        .nav-links a {
            position: relative;
            padding-bottom: 0.2rem;
        }

        .nav-links a::after {
            content: "";
            position: absolute;
            left: 0;
            bottom: 0;
            width: 0;
            height: 2px;
            background-color: var(--accent);
            transition: width 0.2s ease;
        }

        .nav-links a:hover::after {
            width: 100%;
        }

        /* Hero */
        .hero {
            max-width: 1100px;
            margin: 0 auto;
            padding: 3rem 1.5rem 2rem;
            display: grid;
            grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
            gap: 2rem;
            align-items: center;
        }

        .hero-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            background-color: var(--accent-soft);
            color: var(--accent);
            border-radius: 999px;
            padding: 0.35rem 0.85rem;
            font-size: 0.8rem;
            margin-bottom: 1rem;
            font-weight: 500;
        }

        .hero-badge span.icon {
            font-size: 1.1rem;
        }

        .hero-title {
            font-size: clamp(2rem, 3vw + 1rem, 3rem);
            font-weight: 700;
            margin-bottom: 0.75rem;
        }

        .hero-subtitle {
            font-size: 1rem;
            color: var(--muted);
            margin-bottom: 1.5rem;
            max-width: 30rem;
        }

        .hero-cta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            align-items: center;
        }

        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.8rem 1.3rem;
            border-radius: 999px;
            font-weight: 600;
            font-size: 0.95rem;
            cursor: pointer;
            border: 1px solid transparent;
            transition: transform 0.1s ease, box-shadow 0.1s ease, background 0.1s ease, border-color 0.1s ease;
            gap: 0.4rem;
        }

        .btn-primary {
            background-color: var(--accent);
            color: white;
            box-shadow: 0 10px 18px rgba(0,0,0,0.08);
        }

        .btn-primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 14px 25px rgba(0,0,0,0.12);
        }

        .btn-ghost {
            border-color: var(--border);
            background-color: white;
            color: var(--primary);
        }

        .btn-ghost:hover {
            background-color: #f9fafb;
        }

        .hero-note {
            font-size: 0.8rem;
            color: var(--muted);
        }

        .hero-image-wrapper {
            display: flex;
            justify-content: center;
        }

        .hero-card {
            background: radial-gradient(circle at top, #fee2e2 0, #f9fafb 55%, #e5e7eb 100%);
            border-radius: 1.5rem;
            padding: 1.5rem;
            width: 100%;
            max-width: 320px;
            box-shadow: 0 20px 45px rgba(15,23,42,0.15);
            position: relative;
            overflow: hidden;
        }

        .hero-card-tag {
            position: absolute;
            top: 1rem;
            right: 1rem;
            background-color: rgba(15,23,42,0.9);
            color: white;
            padding: 0.3rem 0.7rem;
            border-radius: 999px;
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }

        .book-cover {
            background-color: rgba(255,255,255,0.9);
            border-radius: 0.8rem;
            padding: 1.2rem;
            margin-bottom: 1.1rem;
        }

        .book-spine {
            width: 100%;
            aspect-ratio: 3 / 4;
            border-radius: 0.6rem;
            border: 1px solid rgba(15,23,42,0.1);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            padding: 1rem;
        }

        .book-title {
            font-weight: 600;
            font-size: 1.1rem;
            margin-bottom: 0.5rem;
        }

        .book-author {
            font-size: 0.85rem;
            color: var(--muted);
        }

        .hero-card-footer {
            font-size: 0.8rem;
            color: var(--primary);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .hero-badge-small {
            background-color: rgba(15,23,42,0.06);
            border-radius: 999px;
            padding: 0.25rem 0.6rem;
        }

        /* Sections base */
        section {
            padding: 3rem 1.5rem;
        }

        .section-inner {
            max-width: 1100px;
            margin: 0 auto;
        }

        .section-title {
            font-size: 1.6rem;
            margin-bottom: 0.5rem;
        }

        .section-subtitle {
            color: var(--muted);
            font-size: 0.95rem;
            margin-bottom: 2rem;
        }

        /* Sobre o autor */
        .about-grid {
            display: grid;
            grid-template-columns: minmax(0, 2fr) minmax(0, 1.3fr);
            gap: 2rem;
            align-items: center;
        }

        .about-text p + p {
            margin-top: 0.75rem;
        }

        .about-highlight {
            margin-top: 1rem;
            padding: 0.9rem 1rem;
            border-radius: 0.9rem;
            background-color: white;
            border: 1px solid var(--border);
            font-size: 0.9rem;
        }

        .about-meta {
            font-size: 0.8rem;
            color: var(--muted);
            margin-top: 0.5rem;
        }

        .author-photo {
            width: 220px;
            height: 220px;
            border-radius: 999px;
            border: 4px solid #e5e7eb;
            background: linear-gradient(135deg, #fed7aa, #bfdbfe);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 3rem;
            font-weight: 600;
            margin: 0 auto;
        }

        /* Livros */
        .books-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 1.5rem;
        }

        .book-card {
            background-color: var(--card-bg);
            border-radius: 1rem;
            padding: 1.2rem;
            border: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            box-shadow: 0 6px 14px rgba(15,23,42,0.06);
        }

        .book-card-tag {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--accent);
        }

        .book-card-title {
            font-weight: 600;
            font-size: 1.1rem;
        }

        .book-card-desc {
            font-size: 0.9rem;
            color: var(--muted);
            flex: 1;
        }

        .book-card-meta {
            font-size: 0.8rem;
            color: var(--muted);
        }

        .book-card-actions {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 0.5rem;
        }

        .btn-outline {
            border-radius: 999px;
            padding: 0.6rem 1rem;
            border: 1px solid var(--accent);
            font-size: 0.85rem;
            font-weight: 500;
            background: transparent;
            color: var(--accent);
            cursor: pointer;
            transition: background 0.1s ease, color 0.1s ease;
        }

        .btn-outline:hover {
            background-color: var(--accent);
            color: white;
        }

        /* Depoimentos */
        .testimonials-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 1.5rem;
        }

        .testimonial-card {
            background-color: white;
            border-radius: 1rem;
            padding: 1.2rem;
            border: 1px solid var(--border);
            font-size: 0.9rem;
        }

        .testimonial-author {
            margin-top: 0.8rem;
            font-weight: 500;
        }

        .testimonial-role {
            font-size: 0.8rem;
            color: var(--muted);
        }

        /* Contato */
        .contact-grid {
            display: grid;
            grid-template-columns: minmax(0, 1.6fr) minmax(0, 1.2fr);
            gap: 2rem;
        }

        .contact-card {
            background-color: white;
            border-radius: 1rem;
            border: 1px solid var(--border);
            padding: 1.5rem;
        }

        .contact-card h3 {
            margin-bottom: 0.75rem;
            font-size: 1.1rem;
        }

        .contact-item {
            font-size: 0.9rem;
            margin-bottom: 0.5rem;
        }

        .contact-item span {
            font-weight: 500;
        }

        .contact-form {
            display: grid;
            gap: 0.8rem;
            margin-top: 0.7rem;
        }

        .contact-form label {
            font-size: 0.85rem;
            font-weight: 500;
        }

        .contact-form input,
        .contact-form textarea {
            width: 100%;
            padding: 0.6rem 0.7rem;
            border-radius: 0.6rem;
            border: 1px solid var(--border);
            font-size: 0.9rem;
            font-family: inherit;
        }

        .contact-form textarea {
            min-height: 90px;
            resize: vertical;
        }

        footer {
            border-top: 1px solid var(--border);
            padding: 1.5rem;
            text-align: center;
            font-size: 0.8rem;
            color: var(--muted);
            background-color: #f9fafb;
        }

        /* Responsivo */
        @media (max-width: 900px) {
            .hero {
                grid-template-columns: minmax(0, 1fr);
            }
            .hero-image-wrapper {
                order: -1;
            }
            .about-grid {
                grid-template-columns: minmax(0, 1fr);
            }
            .contact-grid {
                grid-template-columns: minmax(0, 1fr);
            }
            .books-grid,
            .testimonials-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 640px) {
            .nav-links {
                display: none;
            }
            .hero {
                padding-top: 2rem;
            }
            .books-grid,
            .testimonials-grid {
                grid-template-columns: minmax(0, 1fr);
            }
            section {
                padding-inline: 1rem;
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
            <a href="#depoimentos">Leitores</a>
            <a href="#contato">Contato</a>
        </nav>
    </div>
</header>

<main>
    <!-- HERO -->
    <section class="hero">
        <div>
            <div class="hero-badge">
                <span class="icon">📚</span>
                <span>Site oficial de Nicolau Ranvier</span>
            </div>
            <h1 class="hero-title">Histórias que deixam marcas em quem lê.</h1>
            <p class="hero-subtitle">
                Conheça os livros de Nicolau Ranvier e adquira suas obras em versão digital ou impressa,
                diretamente com o autor.
            </p>
            <div class="hero-cta">
                <a href="#livros" class="btn btn-primary">
                    Ver todos os livros
                </a>
                <!-- Substitua o link abaixo pela sua página na Amazon ou outra loja -->
                <a href="#" class="btn btn-ghost">
                    Comprar na Amazon
                </a>
            </div>
            <p class="hero-note">
                Envio para todo o Brasil | E-books disponíveis para leitura imediata.
            </p>
        </div>

        <div class="hero-image-wrapper">
            <div class="hero-card">
                <div class="hero-card-tag">Novo lançamento</div>
                <div class="book-cover">
                    <div class="book-spine">
                        <div class="book-title">Título do Livro Principal</div>
                        <div class="book-author">por Nicolau Ranvier</div>
                    </div>
                </div>
                <div class="hero-card-footer">
                    <div>
                        <div style="font-size:0.8rem; font-weight:600;">Disponível em e-book e físico</div>
                        <div style="font-size:0.75rem; color:var(--muted);">Clique em “Ver todos os livros”</div>
                    </div>
                    <div class="hero-badge-small">Autor brasileiro</div>
                </div>
            </div>
        </div>
    </section>

    <!-- SOBRE O AUTOR -->
    <section id="sobre">
        <div class="section-inner">
            <h2 class="section-title">Sobre Nicolau Ranvier</h2>
            <p class="section-subtitle">
                Um pouco da trajetória, inspirações e visão por trás dos livros.
            </p>
            <div class="about-grid">
                <div class="about-text">
                    <p>
                        Nicolau Ranvier é um autor brasileiro apaixonado por histórias que misturam emoção,
                        reflexão e humanidade. Seus livros exploram temas como relações humanas, escolhas difíceis
                        e o poder transformador da palavra escrita.
                    </p>
                    <p>
                        Com uma escrita envolvente e acessível, Nicolau busca dialogar diretamente com o leitor,
                        criando personagens vivos e tramas que permanecem na memória muito depois da última página.
                    </p>
                    <div class="about-highlight">
                        📌 <strong>Missão:</strong> escrever livros que toquem o coração, provoquem pensamento e
                        inspirem pessoas a enxergarem a própria história com novos olhos.
                        <div class="about-meta">
                            Disponível para palestras, clubes de leitura e parcerias literárias.
                        </div>
                    </div>
                </div>
                <div>
                    <!-- Se tiver uma foto sua, substitua esse bloco por uma <img> -->
                    <div class="author-photo">
                        NR
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- LIVROS -->
    <section id="livros">
        <div class="section-inner">
            <h2 class="section-title">Livros de Nicolau Ranvier</h2>
            <p class="section-subtitle">
                Escolha abaixo o livro que mais combina com você. Clique para comprar em versão digital ou impressa.
            </p>

            <div class="books-grid">
                <!-- LIVRO 1 -->
                <article class="book-card">
                    <div class="book-card-tag">Romance</div>
                    <h3 class="book-card-title">Título do Livro 1</h3>
                    <p class="book-card-desc">
                        Uma breve descrição do livro 1. Fale sobre o protagonista, o conflito principal
                        e o tom da história, despertando curiosidade no leitor.
                    </p>
                    <div class="book-card-meta">
                        ~ 220 páginas · Disponível em e-book e físico
                    </div>
                    <div class="book-card-actions">
                        <!-- Troque os # pelos links reais -->
                        <a href="#" class="btn-outline">Comprar e-book</a>
                        <a href="#" class="btn-outline">Comprar livro físico</a>
                    </div>
                </article>

                <!-- LIVRO 2 -->
                <article class="book-card">
                    <div class="book-card-tag">Ficção contemporânea</div>
                    <h3 class="book-card-title">Título do Livro 2</h3>
                    <p class="book-card-desc">
                        Uma breve descrição do livro 2. Destaque o tema central, o tipo de leitor
                        que vai se identificar e o diferencial da obra.
                    </p>
                    <div class="book-card-meta">
                        ~ 180 páginas · E-book
                    </div>
                    <div class="book-card-actions">
                        <a href="#" class="btn-outline">Comprar agora</a>
                    </div>
                </article>

                <!-- LIVRO 3 -->
                <article class="book-card">
                    <div class="book-card-tag">Não-ficção</div>
                    <h3 class="book-card-title">Título do Livro 3</h3>
                    <p class="book-card-desc">
                        Uma breve descrição do livro 3. Se for desenvolvimento pessoal, espiritualidade ou
                        outro tema, explique claramente o benefício para o leitor.
                    </p>
                    <div class="book-card-meta">
                        ~ 150 páginas · E-book e físico sob demanda
                    </div>
                    <div class="book-card-actions">
                        <a href="#" class="btn-outline">Ver detalhes</a>
                    </div>
                </article>
            </div>
        </div>
    </section>

    <!-- DEPOIMENTOS -->
    <section id="depoimentos">
        <div class="section-inner">
            <h2 class="section-title">O que os leitores dizem</h2>
            <p class="section-subtitle">
                Depoimentos de leitores que já foram tocados pelas histórias de Nicolau Ranvier.
            </p>

            <div class="testimonials-grid">
                <div class="testimonial-card">
                    “Uma leitura que me fez repensar muitas coisas na minha vida. Personagens reais, diálogos profundos
                    e uma escrita leve e envolvente.”
                    <div class="testimonial-author">Leitor A</div>
                    <div class="testimonial-role">via Amazon</div>
                </div>
                <div class="testimonial-card">
                    “Terminei o livro em dois dias. Não conseguia largar! A forma como o autor constrói as cenas é
                    simplesmente incrível.”
                    <div class="testimonial-author">Leitora B</div>
                    <div class="testimonial-role">Clube de leitura</div>
                </div>
                <div class="testimonial-card">
                    “Um daqueles livros que você indica para amigos e familiares. Fiquei emocionado do começo ao fim.”
                    <div class="testimonial-author">Leitor C</div>
                    <div class="testimonial-role">Instagram literário</div>
                </div>
            </div>
        </div>
    </section>

    <!-- CONTATO -->
    <section id="contato">
        <div class="section-inner">
            <h2 class="section-title">Contato e parcerias</h2>
            <p class="section-subtitle">
                Fale diretamente com Nicolau Ranvier para convites, parcerias ou dúvidas sobre os livros.
            </p>

            <div class="contact-grid">
                <div class="contact-card">
                    <h3>Fale comigo</h3>
                    <p class="contact-item">
                        <span>E-mail:</span> <a href="mailto:seuemail@exemplo.com">seuemail@exemplo.com</a>
                    </p>
                    <p class="contact-item">
                        <span>Instagram:</span> <a href="#" target="_blank">@seu_instagram</a>
                    </p>
                    <p class="contact-item">
                        <span>Outras plataformas:</span> Amazon, Skoob, Goodreads
                    </p>
                    <p style="font-size:0.8rem; color:var(--muted); margin-top:0.8rem;">
                        Respondo normalmente em até 2 dias úteis. 😊
                    </p>
                </div>

                <div class="contact-card">
                    <h3>Envie uma mensagem rápida</h3>
                    <!-- Este formulário é apenas visual; para funcionar de verdade precisa ligar a um serviço de envio de e-mail -->
                    <form class="contact-form">
                        <div>
                            <label for="nome">Nome</label>
                            <input id="nome" type="text" placeholder="Seu nome completo">
                        </div>
                        <div>
                            <label for="email">E-mail</label>
                            <input id="email" type="email" placeholder="seuemail@exemplo.com">
                        </div>
                        <div>
                            <label for="mensagem">Mensagem</label>
                            <textarea id="mensagem" placeholder="Escreva sua mensagem..."></textarea>
                        </div>
                        <button type="button" class="btn btn-primary">
                            Enviar mensagem
                        </button>
                    </form>
                </div>
            </div>
        </div>
    </section>
</main>

<footer>
    © <span id="ano-atual"></span> Nicolau Ranvier · Todos os direitos reservados.
</footer>

<script>
    // Atualiza o ano automaticamente
    document.getElementById("ano-atual").textContent = new Date().getFullYear();
</script>

</body>
</html>