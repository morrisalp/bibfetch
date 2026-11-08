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



def test_local_tidy():
    from bibfetch.bibparse import local_tidy
    bib = r"""@inproceedings{k,
  title={Sam audio judge and BioSEN \& friends},
  author={M{\"u}ller, Jan and Dollár, Piotr},
  booktitle={ICASSP 2023-2023 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)},
  pages={1-5},
  year={2023}
}"""
    e = local_tidy(parse_bib(bib)[0])
    assert e.fields["title"] == r"Sam audio judge and {BioSEN} \& friends"
    assert e.fields["author"] == r"M{\"u}ller, Jan and Doll{\'a}r, Piotr"
    assert e.fields["booktitle"] == "Proc. IEEE ICASSP"
    assert e.fields["pages"] == "1--5"


def test_same_author():
    from bibfetch.resolve import _same_author
    assert _same_author("Le Roux", "Roux")
    assert _same_author("Défossez", "Defossez")
    assert not _same_author("Gong", "Gang")
    assert not _same_author("", "Gong")


def test_latex_to_plain():
    from bibfetch.bibparse import latex_to_plain
    assert latex_to_plain(r"Capp{\'e}") == "Cappe"
    assert latex_to_plain(r"M{\"u}ller \& {SDR}") == "Muller & SDR"
    assert latex_to_plain(r"Begu\v{s}") == "Begus"


def test_cr_year():
    from bibfetch.sources import _cr_year
    assert _cr_year({"DOI": "10.1109/icassp.1979.1170788", "created": {"date-parts": [[2005]]}}) == "1979"
    assert _cr_year({"issued": {"date-parts": [[2021, 8]]}}) == "2021"


def test_merge():
    from bibfetch.merge import merge_authors, merge_title_case
    from bibfetch.bibtex import same_numbers
    assert merge_authors("Gray, Augustine and Markel, John", "Gray, A. and Markel, J.") == "Gray, Augustine and Markel, John"
    assert merge_authors(r"Capp{\'e}, Olivier", "Cappe, O.") == r"Capp{\'e}, Olivier"
    assert merge_authors("Le Roux, Jonathan and Wisdom, Scott", "Roux, Jonathan Le and Wisdom, Scott") == "Le Roux, Jonathan and Wisdom, Scott"
    assert merge_authors("Mcewen, Ben", "McEwen, Ben") == "McEwen, Ben"
    assert merge_authors("Defossez, Alexandre", r"D{\'e}fossez, Alexandre") == r"D{\'e}fossez, Alexandre"
    full = "Kirillov, Alexander and Mintun, Eric and Ravi, Nikhila"
    assert merge_authors("Kirillov, Alexander and Mintun, E and others", full) == full
    assert merge_authors("Kirillov, Alexander and Mintun, E and others", full, keep_etal=True) == "Kirillov, Alexander and Mintun, Eric and others"
    assert merge_authors("Smith, John", "Jones, Mary") == "Jones, Mary"
    assert merge_title_case("Parallel WaveGAN: A fast model", "Parallel Wavegan: A Fast Model") == "Parallel {WaveGAN}: A Fast Model"
    assert not same_numbers("DNSMOS P. 835: A metric", "Dnsmos: A metric")


def test_codes_and_month():
    from bibfetch.bibtex import Entry
    assert protect_title("DNSMOS P.835: A metric") == "{DNSMOS} {P}.835: A metric"
    e = Entry("misc", "k", {"title": "x", "month": "jun"})
    assert "month = jun" in e.render() and "{jun}" not in e.render()


def test_review(tmp_path):
    from bibfetch.review import write_review
    a = tmp_path / "a.bbl"; b = tmp_path / "b.bbl"; o = tmp_path / "r.html"
    a.write_text(r"\begin{thebibliography}{1}\bibitem{x} Ast: audio, {\em arXiv}, 2021.\bibitem{y} Same.\end{thebibliography}")
    b.write_text(r"\begin{thebibliography}{1}\bibitem{x} {AST}: audio, {\em Proc. Interspeech}, 2021.\bibitem{y} Same.\end{thebibliography}")
    assert write_review(str(a), str(b), str(o)) == (1, 2)
    t = o.read_text()
    assert "<del>" in t and "<ins>" in t and 'data-key="x"' in t and 'data-key="y"' not in t


def test_review_bib(tmp_path):
    from bibfetch.review import write_review
    a = tmp_path / "a.bbl"; b = tmp_path / "b.bbl"; o = tmp_path / "r.html"
    ba = tmp_path / "a.bib"; bb = tmp_path / "b.bib"
    a.write_text(r"\bibitem{x} Ast, 2021.")
    b.write_text(r"\bibitem{x} {AST}, 2021.")
    ba.write_text("@article{x,\n  title={Ast: {nested} t},\n  year={2021}\n}\n")
    bb.write_text("@inproceedings{x,\n  title = {{AST}: t},\n  year = {2021}\n}\n")
    write_review(str(a), str(b), str(o), before_bib=str(ba), after_bib=str(bb))
    t = o.read_text()
    assert "<details><summary>BibTeX</summary>" in t and "inproceedings" in t and "nested" in t
