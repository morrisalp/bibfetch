from bibfetch.bibparse import arxiv_id, is_preprint, parse_bib
from bibfetch.bibtex import make_key, protect_title, short_venue, tidy_pages, title_similarity, to_latex
from bibfetch.resolve import classify


def test_protect_title():
    assert protect_title("AST: Audio Spectrogram Transformer") == "{AST}: Audio Spectrogram Transformer"
    assert protect_title("BioSEN and FSD50K on wav2vec") == "{BioSEN} and {FSD50K} on wav2vec"
    assert protect_title("Already {Protected} Title") == "Already {Protected} Title"


def test_to_latex():
    assert to_latex("Défossez") == r"D{\'e}fossez"
    assert to_latex("Beguš") == r"Begu{\v s}"
    assert to_latex("A & B 3–5") == r"A \& B 3--5"


def test_venues():
    assert short_venue("Interspeech 2021") == "Proc. Interspeech"
    assert short_venue("ICASSP 2023 - 2023 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)") == "Proc. IEEE ICASSP"
    assert short_venue("2023 International Conference on Machine Learning and Applications (ICMLA)") is None
    assert short_venue("PLOS Computational Biology") is None


def test_misc():
    assert tidy_pages("3291–3295") == "3291--3295"
    assert make_key([("Gong", "Yuan")], "2021", "AST: Audio Spectrogram Transformer") == "gong2021ast"
    assert make_key([("Défossez", "A")], "2020", "Real time speech enhancement") == "defossez2020real"
    assert title_similarity("{SAM} Audio: segment anything", "SAM Audio: Segment Anything") == 1.0


def test_classify():
    assert classify("10.21437/Interspeech.2021-698") == ("doi", "10.21437/Interspeech.2021-698")
    assert classify("https://doi.org/10.48550/arXiv.2104.01778") == ("arxiv", "2104.01778")
    assert classify("https://arxiv.org/abs/2104.01778v3") == ("arxiv", "2104.01778")
    assert classify("2104.01778") == ("arxiv", "2104.01778")
    assert classify("AST: Audio Spectrogram Transformer")[0] == "title"


def test_parse_bib():
    bib = """@article{gong2021ast,
  title={Ast: Audio spectrogram transformer},
  author={Gong, Yuan and Chung, Yu-An and Glass, James},
  journal={arXiv preprint arXiv:2104.01778},
  year={2021}
}
@inproceedings{x, title = "Quoted {Title}", year = 2020}
"""
    items = parse_bib(bib)
    assert [i.key for i in items] == ["gong2021ast", "x"]
    assert is_preprint(items[0]) and not is_preprint(items[1])
    assert arxiv_id(items[0]) == "2104.01778"
    assert items[1].fields["title"] == "Quoted {Title}"


def test_classify_urls():
    assert classify("https://arxiv.org/pdf/2104.01778v2.pdf") == ("arxiv", "2104.01778")
    assert classify("arXiv:2104.01778") == ("arxiv", "2104.01778")


def test_hyphenated():
    assert protect_title("Self-Supervised Learning") == "Self-Supervised Learning"
    assert protect_title("ORCA-CLEAN denoising") == "{ORCA}-{CLEAN} denoising"


def test_split_name():
    from bibfetch.sources import split_name
    assert split_name("Sydney von Arx") == ("von Arx", "Sydney")
    assert split_name("Juan Carlos Niebles") == ("Niebles", "Juan Carlos")
    assert split_name("Ludwig van der Waals") == ("van der Waals", "Ludwig")
