from django.forms import (
    BooleanField,
    CharField,
    ChoiceField,
    Form,
    IntegerField,
    RadioSelect,
)


class NameForm(Form):
    username = CharField(label="Username", max_length=255, required=True)
    username.widget.attrs["class"] = "form-control"
    username.widget.attrs["placeholder"] = "Username"  # Required for the pretty label animation

    CHOICES = [("anime", "Anime"), ("manga", "Manga")]

    anime_or_manga = ChoiceField(choices=CHOICES, widget=RadioSelect)
    anime_or_manga.widget.attrs["class"] = "form-check-input"

    divider_1 = BooleanField(required=False)

    use_watching = BooleanField(required=False, label="Watching", initial=True)
    use_completed = BooleanField(required=False, label="Completed", initial=True)
    use_on_hold = BooleanField(required=False, label="On-Hold", initial=True)
    use_dropped = BooleanField(required=False, label="Dropped", initial=True)
    use_plan_to_watch = BooleanField(required=False, label="Plan to Watch", initial=True)

    use_watching.widget.attrs["class"] = "form-check-input use_toggles"
    use_completed.widget.attrs["class"] = "form-check-input use_toggles"
    use_on_hold.widget.attrs["class"] = "form-check-input use_toggles"
    use_dropped.widget.attrs["class"] = "form-check-input use_toggles"
    use_plan_to_watch.widget.attrs["class"] = "form-check-input use_toggles"

    divider_2 = BooleanField(required=False)

    do_not_return_not_on_list = BooleanField(required=False, label="Not on List", initial=True)
    do_not_return_watching = BooleanField(required=False, label="Watching")
    do_not_return_completed = BooleanField(required=False, label="Completed")
    do_not_return_on_hold = BooleanField(required=False, label="On-Hold")
    do_not_return_dropped = BooleanField(required=False, label="Dropped")
    do_not_return_plan_to_watch = BooleanField(required=False, label="Plan to Watch")

    do_not_return_not_on_list.widget.attrs["class"] = "form-check-input do_not_return_toggles"
    do_not_return_watching.widget.attrs["class"] = "form-check-input do_not_return_toggles"
    do_not_return_completed.widget.attrs["class"] = "form-check-input do_not_return_toggles"
    do_not_return_on_hold.widget.attrs["class"] = "form-check-input do_not_return_toggles"
    do_not_return_dropped.widget.attrs["class"] = "form-check-input do_not_return_toggles"
    do_not_return_plan_to_watch.widget.attrs["class"] = "form-check-input do_not_return_toggles"

    divider_3 = BooleanField(required=False)

    minimum_recs = IntegerField(label="Minimum Recommended", required=True, initial=1)
    ignore_recs_over = IntegerField(label="Ignore Recommendations Over", required=True, initial=100)
    number_of_results = IntegerField(label="Number of Results", required=True, initial=100)

    minimum_recs.widget.attrs["class"] = "form-control"
    ignore_recs_over.widget.attrs["class"] = "form-control"
    number_of_results.widget.attrs["class"] = "form-control"

    minimum_recs.widget.attrs["placeholder"] = "Minimum Recommended"
    ignore_recs_over.widget.attrs["placeholder"] = "Ignore Recommendations Over"
    number_of_results.widget.attrs["placeholder"] = "Number of Results"

    popularity_compensation = BooleanField(required=False, label="Popularity Compensation (WIP)")
    score_compensation = BooleanField(required=False, label="Score Compensation (WIP)")

    popularity_compensation.widget.attrs["class"] = "form-check-input"
    score_compensation.widget.attrs["class"] = "form-check-input"
