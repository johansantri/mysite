import random
from django.shortcuts import render,redirect
from .models import Question, Choice, Score
from django.http import JsonResponse

def quiz_view(request):
    if 'question_ids' not in request.session or not request.session['question_ids']:
        # Shuffle and store question IDs in the session
        questions = list(Question.objects.values_list('id', flat=True))
        random.shuffle(questions)
        request.session['question_ids'] = questions

    # Retrieve the next 5 questions from the shuffled list
    question_ids = request.session['question_ids']
    questions = Question.objects.filter(id__in=question_ids[:5])  # Limit to 5 questions

    return render(request, 'quiz/quiz.html', {'questions': questions})



def check_answer(request, question_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    question_ids = request.session.get('question_ids', [])
    if question_id not in question_ids:
        return JsonResponse({'error': 'Invalid question'}, status=400)

    try:
        question = Question.objects.get(id=question_id)
        selected_choice_id = request.POST.get('choice')
        selected_choice = question.choices.get(id=selected_choice_id)
    except (Question.DoesNotExist, Choice.DoesNotExist, TypeError):
        return JsonResponse({'error': 'Invalid choice or question'}, status=400)

    is_correct = selected_choice.is_correct

    # Initialize session data if not present
    request.session.setdefault('score', 0)
    request.session.setdefault('answered_questions', [])

    answered_questions = set(request.session['answered_questions'])

    if question_id not in answered_questions:
        if is_correct:
            request.session['score'] += 1
        answered_questions.add(question_id)

    request.session['answered_questions'] = list(answered_questions)
    request.session.modified = True

    return render(request, 'quiz/answer.html', {
        'is_correct': is_correct,
        'correct_choice': question.choices.filter(is_correct=True).first(),
    })

def restart_quiz(request):
    # Clear session data
    request.session.pop('score', None)
    request.session.pop('answered_questions', None)
    request.session.pop('question_ids', None)

    # Shuffle and reassign new questions
    questions = list(Question.objects.values_list('id', flat=True))
    random.shuffle(questions)
    request.session['question_ids'] = questions

    return redirect('quiz')





def score_list(request):
    scores = Score.objects.all().order_by('-date')  # Show recent scores first
    return render(request, 'quiz/scores.html', {'scores': scores})


def calculate_grade(score, total_questions):
    if total_questions == 0:
        return "N/A"  # Avoid division by zero
    percentage = (score / total_questions) * 100
    grade_thresholds = [
        (90, "A"),
        (80, "B"),
        (70, "C"),
        (60, "D"),
    ]
    for threshold, grade in grade_thresholds:
        if percentage >= threshold:
            return grade
    return "F"


def quiz_result(request):
    score = request.session.get('score', 0)
    answered_questions = request.session.get('answered_questions', [])
    total_questions = len(answered_questions)

    # Calculate the grade only for answered questions
    grade = calculate_grade(score, total_questions)

    # Save the score and grade to the database
    try:
        Score.objects.create(
            user=request.user.username if request.user.is_authenticated else f"Anonymous-{random.randint(1000, 9999)}",
            score=score,
            total_questions=total_questions,
            grade=grade,
        )
    except Exception as e:
        # Handle any unexpected errors during score saving
        print(f"Error saving score: {e}")

    # Clear session data
    request.session.pop('score', None)
    request.session.pop('answered_questions', None)
    request.session.pop('question_ids', None)

    return render(request, 'quiz/result.html', {
        'score': score,
        'total_questions': total_questions,
        'grade': grade,
    })


