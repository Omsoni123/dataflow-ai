"use client";































import { useEffect, useRef, useState, type ChangeEvent, type FormEvent, type ReactNode } from "react";















import { useRouter } from "next/navigation";































type DynamicKpi = {
  key: string;
  label: string;
  value: number | string | { start?: string; end?: string } | null;
  format: "number" | "decimal" | "percent" | "currency" | "date" | "text";
  aggregation: string;
  column?: string | null;
  reason?: string;
};


type ChatMessage = {







  question: string;







  answer: string;







};















type DatasetProfile = {







  row_count: number;







  column_count: number;







  missing_value_count: number;







  duplicate_row_count: number;







  columns: {







    name: string;







    dtype: string;







    missing: number;







    unique_values: number;







  }[];







  missing_values_by_column: Record<string, number>;







  numeric_columns: string[];







  text_columns: string[];







  date_columns: string[];







  boolean_columns: string[];







};

















type DatasetIntelligence = {

  dataset_domain?: {

    domain?: string;

    confidence?: number;

  };

  row_count?: number;

  column_count?: number;

  role_counts?: Record<string, number>;

  columns?:
    | Array<{
        name?: string;
        role?: string;
        semantic_tags?: string[];
      }>
    | Record<
        string,
        {
          role?: string;
          semantic_tags?: string[];
          [key: string]: unknown;
        }
      >;

  metric_candidates?: Array<{

    column?: string;

    name?: string;

    role?: string;

    reason?: string;

  }>;

  analysis_opportunities?: Array<{

    type?: string;

    name?: string;

    description?: string;

  }>;

};



type CleaningSummary = {







  before: {







    row_count: number;







    column_count: number;







    missing_value_count: number;







    duplicate_row_count: number;







  };







  after: {







    row_count: number;







    column_count: number;







    missing_value_count: number;







    duplicate_row_count: number;







  };







  changes: {







    rows_removed: number;







    duplicate_rows_removed: number;







    global_missing_rows_removed: number;







    column_specific_rows_removed: Record<string, number>;







    filled_values: Record<string, { count: number; fill_value: string }>;







  };







};















type ColumnAction = "keep" | "drop_rows" | "fill";































// Production-ready API configuration















const API_URL = process.env.NEXT_PUBLIC_API_URL;































type BillingUser = {
  user_id?: string;
  name?: string;
  email?: string;
  plan?: "free" | "pro" | string;
  ai_questions_used?: number;
  subscription_status?: string;
  razorpay_subscription_id?: string | null;
  is_admin?: boolean;
};

type RazorpayCheckoutResponse = {
  razorpay_payment_id: string;
  razorpay_subscription_id: string;
  razorpay_signature: string;
};



type SuggestedQuestionColumn = {
  name?: string;
  role?: string;
  semantic_tags?: string[];
};

function humanizeColumnName(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function buildSuggestedQuestions(
  intelligence: DatasetIntelligence | null
): string[] {
  if (!intelligence) return [];

  // The backend returns `columns` as an object keyed by column name,
  // while older responses may return it as an array. Normalize both shapes
  // before using Array methods such as .find().
  const rawColumns = intelligence.columns ?? [];
  const columns: SuggestedQuestionColumn[] = Array.isArray(rawColumns)
    ? rawColumns
    : Object.entries(rawColumns).map(([name, info]) => ({
        name,
        ...(info ?? {}),
      }));

  const metrics = Array.isArray(intelligence.metric_candidates)
    ? intelligence.metric_candidates
    : [];
  const questions: string[] = [];

  const findColumnByTag = (tag: string) =>
    columns.find((column) => (column.semantic_tags ?? []).includes(tag));

  const findColumnByKeywords = (keywords: string[]) =>
    columns.find((column) => {
      const name = (column.name ?? "").toLowerCase();
      return keywords.some((keyword) => name.includes(keyword));
    });

  const findMetricByKeywords = (keywords: string[]) =>
    metrics.find((metric) => {
      const value = `${metric.column ?? ""} ${metric.name ?? ""}`.toLowerCase();
      return keywords.some((keyword) => value.includes(keyword));
    });

  const personColumn =
    findColumnByTag("person") ??
    findColumnByKeywords(["employee", "customer", "student", "patient", "user", "member"]);

  const categoryColumn =
    findColumnByTag("category") ??
    columns.find((column) => column.role === "categorical");

  const locationColumn = findColumnByTag("location");
  const dateColumn = columns.find((column) => column.role === "datetime");

  const amountMetric =
    findMetricByKeywords([
      "salary", "revenue", "sales", "profit", "amount", "price", "cost", "income", "expense",
    ]) ?? metrics[0];

  const quantityMetric = findMetricByKeywords([
    "quantity", "qty", "units", "count", "age", "days", "hours", "score", "rating",
  ]);

  if (personColumn?.name) {
    questions.push(`How many unique ${humanizeColumnName(personColumn.name)} are there?`);
  }

  if (amountMetric?.column) {
    questions.push(`What is the average ${humanizeColumnName(amountMetric.column)}?`);
  }

  if (categoryColumn?.name && amountMetric?.column) {
    questions.push(
      `Which ${humanizeColumnName(categoryColumn.name)} has the highest average ${humanizeColumnName(amountMetric.column)}?`
    );
  }

  if (categoryColumn?.name) {
    questions.push(`Which ${humanizeColumnName(categoryColumn.name)} has the most records?`);
  }

  if (locationColumn?.name && amountMetric?.column) {
    questions.push(
      `Which ${humanizeColumnName(locationColumn.name)} has the highest ${humanizeColumnName(amountMetric.column)}?`
    );
  }

  if (dateColumn?.name && amountMetric?.column) {
    questions.push(
      `How does ${humanizeColumnName(amountMetric.column)} change over ${humanizeColumnName(dateColumn.name)}?`
    );
  }

  if (quantityMetric?.column && quantityMetric.column !== amountMetric?.column) {
    questions.push(`What is the average ${humanizeColumnName(quantityMetric.column)}?`);
  }

  return Array.from(new Set(questions)).slice(0, 4);
}

export default function Dashboard() {















  const router = useRouter();















  const fileInputRef = useRef<HTMLInputElement>(null);































  const [uploading, setUploading] = useState(false);















  const [asking, setAsking] = useState(false);































  const [error, setError] = useState("");















  const [aiError, setAiError] = useState("");































  const [fileName, setFileName] = useState("");







  const [datasetFile, setDatasetFile] = useState<File | null>(null);







  const [kpis, setKpis] = useState<DynamicKpi[]>([]);







  const [profile, setProfile] = useState<DatasetProfile | null>(null);

  const [intelligence, setIntelligence] = useState<DatasetIntelligence | null>(null);

  const [intelligenceLoading, setIntelligenceLoading] = useState(false);

  const [intelligenceError, setIntelligenceError] = useState("");

  const suggestedQuestions = buildSuggestedQuestions(intelligence);









  const [missingAction, setMissingAction] = useState<"keep" | "drop_rows">("keep");







  const [duplicateAction, setDuplicateAction] = useState<"keep" | "drop">("keep");







  const [columnActions, setColumnActions] = useState<Record<string, ColumnAction>>({});







  const [fillValues, setFillValues] = useState<Record<string, string>>({});







  const [cleaningPreview, setCleaningPreview] = useState<CleaningSummary | null>(null);







  const [cleanedProfile, setCleanedProfile] = useState<DatasetProfile | null>(null);







  const [cleaning, setCleaning] = useState(false);







  const [cleaningApplied, setCleaningApplied] = useState(false);

  const [downloadingCleaned, setDownloadingCleaned] = useState(false);































  const [question, setQuestion] = useState("");















  const [answer, setAnswer] = useState("");















  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);

  // ==========================================================
  // BILLING / PLAN
  // ==========================================================

  const [billingUser, setBillingUser] = useState<BillingUser | null>(null);
  const [billingLoading, setBillingLoading] = useState(false);
  const [billingError, setBillingError] = useState("");
  const [billingSuccess, setBillingSuccess] = useState("");































  // ==========================================================















  // API CONFIGURATION















  // ==========================================================































  function getApiUrl() {















    if (!API_URL) {















      throw new Error(















        "API URL is not configured. Please set NEXT_PUBLIC_API_URL."















      );















    }































    return API_URL.replace(/\/+$/, "");















  }































  // ==========================================================















  // AUTH















  // ==========================================================































  function getToken() {















    if (typeof window === "undefined") {















      return null;















    }































    return localStorage.getItem("access_token");















  }































  useEffect(() => {
    async function loadBillingUser() {
      const token = getToken();

      if (!token) return;

      try {
        const apiUrl = getApiUrl();
        const response = await fetch(`${apiUrl}/auth/me`, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        const data = await response.json().catch(() => ({}));

        if (response.status === 401) {
          localStorage.removeItem("access_token");
          router.push("/login");
          return;
        }

        if (!response.ok) {
          throw new Error(data.detail || "Unable to load account information.");
        }

        setBillingUser(data.user ?? data);
      } catch (err) {
        setBillingError(
          err instanceof Error
            ? err.message
            : "Unable to load account information."
        );
      }
    }

    void loadBillingUser();
  }, []);

  async function loadRazorpayScript(): Promise<boolean> {
    if (typeof window === "undefined") return false;

    if ((window as any).Razorpay) return true;

    return new Promise((resolve) => {
      const script = document.createElement("script");
      script.src = "https://checkout.razorpay.com/v1/checkout.js";
      script.async = true;
      script.onload = () => resolve(true);
      script.onerror = () => resolve(false);
      document.body.appendChild(script);
    });
  }

  async function upgradeToPro() {
    const token = getToken();

    if (!token) {
      router.push("/login");
      return;
    }

    if (billingUser?.plan === "pro") return;

    setBillingLoading(true);
    setBillingError("");
    setBillingSuccess("");

    try {
      const apiUrl = getApiUrl();

      const razorpayLoaded = await loadRazorpayScript();

      if (!razorpayLoaded) {
        throw new Error("Unable to load Razorpay Checkout. Please try again.");
      }

      const subscriptionResponse = await fetch(
        `${apiUrl}/billing/create-subscription`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const subscriptionData = await subscriptionResponse
        .json()
        .catch(() => ({}));

      if (subscriptionResponse.status === 401) {
        localStorage.removeItem("access_token");
        router.push("/login");
        return;
      }

      if (!subscriptionResponse.ok) {
        throw new Error(
          subscriptionData.detail || "Unable to create Pro subscription."
        );
      }

      const razorpay = new (window as any).Razorpay({
        key: subscriptionData.razorpay_key_id,
        subscription_id: subscriptionData.subscription_id,
        name: "DataFlow AI",
        description: "DataFlow AI Pro — ₹499/month",
        prefill: {
          name: billingUser?.name || "",
          email: billingUser?.email || "",
        },
        notes: {
          plan: "pro",
          user_id: billingUser?.user_id || "",
        },
        theme: {
          color: "#7c3aed",
        },
        handler: async (response: RazorpayCheckoutResponse) => {
          try {
            setBillingError("");
            setBillingSuccess("");

            const verifyResponse = await fetch(
              `${apiUrl}/billing/verify-subscription`,
              {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify(response),
              }
            );

            const verifyData = await verifyResponse
              .json()
              .catch(() => ({}));

            if (verifyResponse.status === 401) {
              localStorage.removeItem("access_token");
              router.push("/login");
              return;
            }

            if (!verifyResponse.ok) {
              throw new Error(
                verifyData.detail || "Payment verification failed."
              );
            }

            setBillingUser((previous) => ({
              ...(previous ?? {}),
              plan: "pro",
              subscription_status: "active",
              razorpay_subscription_id:
                response.razorpay_subscription_id,
            }));

            setBillingSuccess(
              "Payment successful. DataFlow AI Pro is now active."
            );
          } catch (err) {
            setBillingError(
              err instanceof Error
                ? err.message
                : "Payment verification failed."
            );
          } finally {
            setBillingLoading(false);
          }
        },
        modal: {
          ondismiss: () => {
            setBillingLoading(false);
          },
        },
      });

      razorpay.open();
    } catch (err) {
      setBillingLoading(false);
      setBillingError(
        err instanceof Error
          ? err.message
          : "Unable to start the Pro subscription."
      );
    }
  }

  function logout() {















    localStorage.removeItem("access_token");















    router.push("/");















  }































  // ==========================================================















  // FILE PICKER















  // ==========================================================































  function openFilePicker() {















    setError("");















    fileInputRef.current?.click();















  }































  // ==========================================================















  // UPLOAD DATASET















  // ==========================================================































  async function handleFileUpload(















    event: ChangeEvent<HTMLInputElement>















  ) {















    const file = event.target.files?.[0];































    if (!file) {















      return;















    }































    if (!file.name.toLowerCase().endsWith(".csv")) {















      setError("Please upload a CSV file.");















      event.target.value = "";















      return;















    }































    const token = getToken();































    if (!token) {















      setError("Your session has expired. Please log in again.");















      return;















    }































    setUploading(true);















    setError("");































    try {















      const apiUrl = getApiUrl();































      const formData = new FormData();















      formData.append("file", file);































      const response = await fetch(`${apiUrl}/datasets/inspect`, {















        method: "POST",















        headers: {















          Authorization: `Bearer ${token}`,















        },















        body: formData,















      });































      const data = await response.json().catch(() => ({}));































      if (response.status === 401) {















        localStorage.removeItem("access_token");















        router.push("/login");















        return;















      }































      if (!response.ok) {















        throw new Error(















          data.detail || "Dataset inspection failed."















        );















      }































      setFileName(file.name);







      setDatasetFile(file);







      setProfile(data.profile);

      setIntelligence(null);

      setIntelligenceError("");

      setIntelligenceLoading(true);



      // Generate universal dataset intelligence for the inspected CSV.

      // This is separate from cleaning so the existing cleaning workflow remains unchanged.

      try {

        const intelligenceFormData = new FormData();

        intelligenceFormData.append("file", file);



        const intelligenceResponse = await fetch(`${apiUrl}/datasets/intelligence`, {

          method: "POST",

          headers: {

            Authorization: `Bearer ${token}`,

          },

          body: intelligenceFormData,

        });



        const intelligenceData = await intelligenceResponse.json().catch(() => ({}));



        if (intelligenceResponse.status === 401) {

          localStorage.removeItem("access_token");

          router.push("/login");

          return;

        }



        if (!intelligenceResponse.ok) {

          throw new Error(

            intelligenceData.detail || "Dataset intelligence analysis failed."

          );

        }



        setIntelligence(intelligenceData.intelligence ?? null);

      } catch (intelligenceErr) {

        // Intelligence is additive at this stage. Do not break inspection or cleaning.

        setIntelligenceError(

          intelligenceErr instanceof Error

            ? intelligenceErr.message

            : "Dataset intelligence analysis failed."

        );

      } finally {

        setIntelligenceLoading(false);

      }







      // Generate universal KPI cards independently from dataset intelligence.
      try {
        const kpiFormData = new FormData();
        kpiFormData.append("file", file);

        const kpiResponse = await fetch(`${apiUrl}/datasets/dynamic-kpis`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: kpiFormData,
        });

        const kpiData = await kpiResponse.json().catch(() => ({}));

        if (kpiResponse.status === 401) {
          localStorage.removeItem("access_token");
          router.push("/login");
          return;
        }

        if (!kpiResponse.ok) {
          throw new Error(kpiData.detail || "Dynamic KPI generation failed.");
        }

        setKpis(kpiData.kpis ?? []);
      } catch (kpiErr) {
        setError(
          kpiErr instanceof Error
            ? kpiErr.message
            : "Dynamic KPI generation failed."
        );
        setKpis([]);
      }







      setCleaningPreview(null);







      setCleanedProfile(null);



      setCleaningApplied(false);







      setMissingAction("keep");







      setDuplicateAction("keep");







      setColumnActions({});







      setFillValues({});































      // Reset AI workspace for the new dataset















      setAnswer("");















      setChatHistory([]);















      setAiError("");















    } catch (err) {















      setError(















        err instanceof Error















          ? err.message















          : "Something went wrong while uploading the dataset."















      );















    } finally {















      setUploading(false);































      // Allow same file to be selected again















      event.target.value = "";















    }















  }































  // ==========================================================







  // CLEANING PREVIEW







  // ==========================================================















  function buildCleaningDecisions() {



    if (!profile) {



      throw new Error("Please inspect a dataset first.");



    }







    return {



      missing_values: missingAction,



      duplicate_rows: duplicateAction,



      columns: profile.columns



        .filter((column) => column.missing > 0)



        .map((column) => ({



          column: column.name,



          action: columnActions[column.name] ?? "keep",



          fill_value:



            columnActions[column.name] === "fill"



              ? (fillValues[column.name] ?? "")



              : null,



        })),



    };



  }







  async function previewCleaning() {



    if (!datasetFile || !profile) {



      setError("Please inspect a dataset first.");



      return;



    }







    const token = getToken();



    if (!token) {



      setError("Your session has expired. Please log in again.");



      return;



    }







    let decisions;



    try {



      decisions = buildCleaningDecisions();



    } catch (err) {



      setError(err instanceof Error ? err.message : "Invalid cleaning decisions.");



      return;



    }







    const invalidFill = decisions.columns.find(



      (item) => item.action === "fill" && !item.fill_value?.trim()



    );







    if (invalidFill) {



      setError(`Enter a fill value for ${invalidFill.column}.`);



      return;



    }







    setCleaning(true);



    setError("");







    try {



      const apiUrl = getApiUrl();



      const formData = new FormData();







      formData.append("file", datasetFile);



      formData.append("decisions", JSON.stringify(decisions));







      const response = await fetch(`${apiUrl}/datasets/clean`, {



        method: "POST",



        headers: { Authorization: `Bearer ${token}` },



        body: formData,



      });







      const data = await response.json().catch(() => ({}));







      if (response.status === 401) {



        localStorage.removeItem("access_token");



        router.push("/login");



        return;



      }







      if (!response.ok) {



        throw new Error(data.detail || "Cleaning preview failed.");



      }







      setCleaningPreview(data.cleaning_summary);



      setCleanedProfile(data.cleaned_profile);



      setCleaningApplied(false);



    } catch (err) {



      setError(err instanceof Error ? err.message : "Cleaning preview failed.");



    } finally {



      setCleaning(false);



    }



  }







  async function applyCleaning() {



    if (!datasetFile || !profile || !cleaningPreview) {



      setError("Please preview the cleaning before applying it.");



      return;



    }







    const token = getToken();



    if (!token) {



      setError("Your session has expired. Please log in again.");



      return;



    }







    let decisions;



    try {



      decisions = buildCleaningDecisions();



    } catch (err) {



      setError(err instanceof Error ? err.message : "Invalid cleaning decisions.");



      return;



    }







    const invalidFill = decisions.columns.find(



      (item) => item.action === "fill" && !item.fill_value?.trim()



    );







    if (invalidFill) {



      setError(`Enter a fill value for ${invalidFill.column}.`);



      return;



    }







    setCleaning(true);



    setError("");







    try {



      const apiUrl = getApiUrl();



      const formData = new FormData();







      formData.append("file", datasetFile);



      formData.append("decisions", JSON.stringify(decisions));







      const response = await fetch(`${apiUrl}/datasets/apply-cleaning`, {



        method: "POST",



        headers: { Authorization: `Bearer ${token}` },



        body: formData,



      });







      const data = await response.json().catch(() => ({}));







      if (response.status === 401) {



        localStorage.removeItem("access_token");



        router.push("/login");



        return;



      }







      if (!response.ok) {



        throw new Error(data.detail || "Failed to apply cleaning.");



      }







      setCleaningApplied(true);







      if (data.cleaned_profile) {



        setCleanedProfile(data.cleaned_profile);



      }







      setError("");



    } catch (err) {



      setError(err instanceof Error ? err.message : "Failed to apply cleaning.");



    } finally {



      setCleaning(false);



    }



  }







  async function downloadCleanedDataset() {
    if (!datasetFile || !profile || !cleaningPreview || !cleaningApplied) {
      setError("Please apply the cleaning before downloading the cleaned dataset.");
      return;
    }

    const token = getToken();

    if (!token) {
      setError("Your session has expired. Please log in again.");
      return;
    }

    let decisions;

    try {
      decisions = buildCleaningDecisions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid cleaning decisions.");
      return;
    }

    const invalidFill = decisions.columns.find(
      (item) => item.action === "fill" && !item.fill_value?.trim()
    );

    if (invalidFill) {
      setError(`Enter a fill value for ${invalidFill.column}.`);
      return;
    }

    setDownloadingCleaned(true);
    setError("");

    try {
      const apiUrl = getApiUrl();
      const formData = new FormData();

      formData.append("file", datasetFile);
      formData.append("decisions", JSON.stringify(decisions));

      const response = await fetch(`${apiUrl}/datasets/download-cleaned`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (response.status === 401) {
        localStorage.removeItem("access_token");
        router.push("/login");
        return;
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail || "Unable to download the cleaned dataset."
        );
      }

      const blob = await response.blob();

      if (!blob.size) {
        throw new Error("The cleaned dataset download was empty.");
      }

      const contentDisposition = response.headers.get("Content-Disposition");
      const fileMatch = contentDisposition?.match(/filename="?([^"]+)"?/i);
      const downloadName =
        fileMatch?.[1] ||
        `cleaned_${datasetFile.name.replace(/\.csv$/i, "")}.csv`;

      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = downloadUrl;
      link.download = downloadName;
      document.body.appendChild(link);
      link.click();
      link.remove();

      window.URL.revokeObjectURL(downloadUrl);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to download the cleaned dataset."
      );
    } finally {
      setDownloadingCleaned(false);
    }
  }


  function setColumnAction(column: string, action: ColumnAction) {







    setColumnActions((previous) => ({ ...previous, [column]: action }));







  }















  async function askAI(customQuestion?: string) {















    const finalQuestion = (















      customQuestion ?? question















    ).trim();































    if (!finalQuestion) {















      return;















    }































    const token = getToken();































    if (!token) {















      setAiError("Your session has expired. Please log in again.");















      return;















    }































    if (kpis.length === 0) {















      setAiError("Please upload a dataset first.");















      return;















    }































    // Free users get exactly one AI Analyst question.
    // Pro users have unlimited AI access.
    if (
      !billingUser?.is_admin &&
      billingUser?.plan !== "pro" &&
      (billingUser?.ai_questions_used ?? 0) >= 1
    ) {
      setAiError(
        "Your free AI Analyst question has been used. Upgrade to Pro for unlimited AI access."
      );
      return;
    }

    setAsking(true);















    setAiError("");















    setAnswer("");































    try {















      const apiUrl = getApiUrl();































      const response = await fetch(`${apiUrl}/datasets/ask`, {















        method: "POST",















        headers: {















          "Content-Type": "application/json",















          Authorization: `Bearer ${token}`,















        },















        body: JSON.stringify({















          question: finalQuestion,















        }),















      });































      const data = await response.json().catch(() => ({}));































      if (response.status === 401) {















        localStorage.removeItem("access_token");















        router.push("/login");















        return;















      }































      if (!response.ok) {















        throw new Error(















          data.detail || "AI analysis failed."















        );















      }































      const newAnswer = data.answer;

      if (!billingUser?.is_admin && billingUser?.plan !== "pro") {
        setBillingUser((previous) => ({
          ...(previous ?? {}),
          ai_questions_used: (previous?.ai_questions_used ?? 0) + 1,
        }));
      }

































      setAnswer(newAnswer);































      setChatHistory((previous) => [















        ...previous,















        {















          question: finalQuestion,















          answer: newAnswer,















        },















      ]);































      setQuestion("");















    } catch (err) {















      setAiError(















        err instanceof Error















          ? err.message















          : "Something went wrong while asking AI."















      );















    } finally {















      setAsking(false);















    }















  }































  function handleQuestionSubmit(















    event: FormEvent<HTMLFormElement>















  ) {















    event.preventDefault();















    askAI();















  }































  // ==========================================================















  // UI















  // ==========================================================































  return (















    <main className="min-h-screen bg-[#07050d] text-white">































      {/* Hidden file input */}















      <input















        ref={fileInputRef}















        type="file"















        accept=".csv"















        onChange={handleFileUpload}















        className="hidden"















      />































      {/* =====================================================















          NAVIGATION















      ===================================================== */}































      <nav className="border-b border-white/[0.07] bg-[#07050d]/90 backdrop-blur-xl">















        <div className="mx-auto flex h-[72px] max-w-[1500px] items-center justify-between px-6 lg:px-10">































          <div className="flex items-center gap-3">































            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 via-purple-600 to-fuchsia-600">















              <span className="font-bold">D</span>















            </div>































            <div>















              <div className="text-[17px] font-semibold">















                DataFlow{" "}















                <span className="text-purple-400">















                  AI















                </span>















              </div>































              <div className="text-[9px] uppercase tracking-[0.25em] text-white/30">















                Intelligent Analytics















              </div>















            </div>































          </div>































          <button















            onClick={logout}















            className="rounded-lg px-4 py-2 text-sm text-white/50 transition hover:bg-white/[0.05] hover:text-white"















          >















            Logout















          </button>































        </div>















      </nav>































      {/* =====================================================















          DASHBOARD















      ===================================================== */}































      <div className="mx-auto max-w-[1500px] px-6 py-8 lg:px-10">































        {/* Header */}















        <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-center">































          <div>















            <p className="text-xs uppercase tracking-[0.25em] text-purple-300/60">















              Workspace















            </p>































            <h1 className="mt-2 text-3xl font-semibold tracking-tight">















              Analytics Dashboard















            </h1>































            <p className="mt-2 text-sm text-white/40">















              Upload your data and turn it into actionable insights.















            </p>















          </div>































          <div className="flex flex-col items-stretch gap-3 sm:items-end">
            {billingUser?.is_admin ? (
              <div className="rounded-xl border border-amber-400/20 bg-amber-500/[0.06] px-4 py-3 text-right">
                <p className="text-xs font-medium text-amber-200">
                  Developer access
                </p>
                <p className="mt-1 text-[11px] text-white/35">
                  Unlimited AI · No payment required
                </p>
              </div>
            ) : billingUser?.plan === "pro" ? (
              <div className="rounded-xl border border-emerald-400/15 bg-emerald-500/[0.05] px-4 py-3 text-right">
                <p className="text-xs font-medium text-emerald-200">
                  Pro plan active
                </p>
                <p className="mt-1 text-[11px] text-white/35">
                  Unlimited AI Analyst access
                </p>
              </div>
            ) : (
              <div className="rounded-xl border border-purple-400/15 bg-purple-500/[0.05] px-4 py-3 text-right">
                <p className="text-xs font-medium text-purple-200">
                  Free plan
                </p>
                <p className="mt-1 text-[11px] text-white/35">
                  {Math.max(
                    0,
                    1 - (billingUser?.ai_questions_used ?? 0)
                  )}{" "}
                  free AI question remaining
                </p>
              </div>
            )}

            <button
              onClick={openFilePicker}
              disabled={uploading}
              className="rounded-xl bg-gradient-to-r from-purple-600 to-violet-600 px-5 py-3 text-sm font-semibold shadow-lg shadow-purple-900/20 transition hover:from-purple-500 hover:to-violet-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {uploading ? "Inspecting..." : "+ Add Data"}
            </button>
          </div>































        </div>































        {(billingError || billingSuccess) && (
          <div className="mt-5 space-y-2">
            {billingError && (
              <div className="rounded-xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
                {billingError}
              </div>
            )}
            {billingSuccess && (
              <div className="rounded-xl border border-emerald-400/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
                {billingSuccess}
              </div>
            )}
          </div>
        )}

        {/* =================================================















            DATASET SECTION















        ================================================= */}































        <section className="mt-8 rounded-3xl border border-purple-400/10 bg-gradient-to-b from-purple-500/[0.06] to-white/[0.015] p-8">































          {!fileName ? (































            <div className="mx-auto max-w-2xl py-16 text-center">































              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-purple-400/20 bg-purple-500/10 text-2xl text-purple-300">















                ↑















              </div>































              <h2 className="mt-6 text-2xl font-semibold">















                Your analytics workspace is ready















              </h2>































              <p className="mx-auto mt-3 max-w-lg text-sm leading-6 text-white/40">















                Upload a CSV dataset to automatically clean your















                data, calculate business metrics, and start asking















                questions with AI.















              </p>































              <button















                onClick={openFilePicker}















                disabled={uploading}















                className="mt-7 rounded-xl bg-white px-5 py-3 text-sm font-semibold text-black transition hover:bg-white/90 disabled:cursor-not-allowed disabled:opacity-50"















              >















                {uploading ? "Inspecting..." : "Upload CSV"}















              </button>































              {uploading && (















                <p className="mt-4 text-xs text-purple-300">















                  Inspecting your dataset...















                </p>















              )}































              {error && (















                <div className="mx-auto mt-5 max-w-lg rounded-xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">















                  {error}















                </div>















              )}































            </div>































          ) : (















            <div>







              <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">







                <div>







                  <div className="flex items-center gap-2">







                    <span className="h-2 w-2 rounded-full bg-emerald-400" />







                    <span className="text-sm font-medium text-emerald-300">







                      Dataset inspected







                    </span>







                  </div>







                  <h2 className="mt-3 text-xl font-semibold">{fileName}</h2>







                  <p className="mt-1 text-xs text-white/30">







                    Review data quality before cleaning or storing your dataset.







                  </p>







                </div>







                <button







                  onClick={openFilePicker}







                  disabled={uploading || cleaning}







                  className="rounded-xl border border-white/10 bg-white/[0.04] px-5 py-3 text-sm font-medium text-white/70 transition hover:border-purple-400/20 hover:text-white disabled:opacity-50"







                >







                  {uploading ? "Inspecting..." : "Upload New Dataset"}







                </button>







              </div>















              {profile && (







                <>







                  <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">







                    <QualityCard label="Rows" value={profile.row_count.toLocaleString("en-IN")} />







                    <QualityCard label="Columns" value={profile.column_count.toLocaleString("en-IN")} />







                    <QualityCard label="Missing Values" value={profile.missing_value_count.toLocaleString("en-IN")} />







                    <QualityCard label="Duplicate Rows" value={profile.duplicate_row_count.toLocaleString("en-IN")} />







                  </div>















                  <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">







                    <QualityCard label="Numeric Columns" value={profile.numeric_columns.length.toString()} />







                    <QualityCard label="Text Columns" value={profile.text_columns.length.toString()} />







                    <QualityCard label="Date Columns" value={profile.date_columns.length.toString()} />







                    <QualityCard label="Boolean Columns" value={profile.boolean_columns.length.toString()} />







                  </div>















                  <div className="mt-6 rounded-2xl border border-white/[0.07] bg-black/20 p-5">







                    <div className="flex items-center justify-between gap-3">







                      <div>







                        <h3 className="font-semibold">Missing values</h3>







                        <p className="mt-1 text-xs text-white/30">







                          Choose what DataFlow AI should do with missing values.







                        </p>







                      </div>







                      <span className="text-sm text-white/40">{profile.missing_value_count} found</span>







                    </div>







                    <div className="mt-4 flex flex-wrap gap-2">







                      <ChoiceButton active={missingAction === "keep"} onClick={() => setMissingAction("keep")}>Keep</ChoiceButton>







                      <ChoiceButton active={missingAction === "drop_rows"} onClick={() => setMissingAction("drop_rows")}>Remove rows</ChoiceButton>







                    </div>







                  </div>















                  <div className="mt-4 rounded-2xl border border-white/[0.07] bg-black/20 p-5">







                    <div className="flex items-center justify-between gap-3">







                      <div>







                        <h3 className="font-semibold">Duplicate rows</h3>







                        <p className="mt-1 text-xs text-white/30">







                          Remove only exact duplicate rows. IDs with multiple line items are not treated as duplicates unless the full row matches.







                        </p>







                      </div>







                      <span className="text-sm text-white/40">{profile.duplicate_row_count} found</span>







                    </div>







                    <div className="mt-4 flex flex-wrap gap-2">







                      <ChoiceButton active={duplicateAction === "keep"} onClick={() => setDuplicateAction("keep")}>Keep duplicates</ChoiceButton>







                      <ChoiceButton active={duplicateAction === "drop"} onClick={() => setDuplicateAction("drop")}>Remove duplicates</ChoiceButton>







                    </div>







                  </div>















                  <div className="mt-4 rounded-2xl border border-white/[0.07] bg-black/20 p-5">







                    <div>







                      <h3 className="font-semibold">Column-level decisions</h3>







                      <p className="mt-1 text-xs text-white/30">







                        Override the global missing-value rule for individual columns.







                      </p>







                    </div>















                    <div className="mt-4 space-y-3">







                      {profile.columns.filter((column) => column.missing > 0).map((column) => {







                        const action = columnActions[column.name] ?? "keep";







                        return (







                          <div key={column.name} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">







                            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">







                              <div>







                                <p className="text-sm font-medium">{column.name}</p>







                                <p className="mt-1 text-xs text-white/30">{column.missing} missing values · {column.dtype}</p>







                              </div>







                              <div className="flex flex-wrap gap-2">







                                <ChoiceButton active={action === "keep"} onClick={() => setColumnAction(column.name, "keep")}>Keep</ChoiceButton>







                                <ChoiceButton active={action === "drop_rows"} onClick={() => setColumnAction(column.name, "drop_rows")}>Drop rows</ChoiceButton>







                                <ChoiceButton active={action === "fill"} onClick={() => setColumnAction(column.name, "fill")}>Fill</ChoiceButton>







                              </div>







                            </div>







                            {action === "fill" && (







                              <input







                                value={fillValues[column.name] ?? ""}







                                onChange={(event) => setFillValues((previous) => ({ ...previous, [column.name]: event.target.value }))}







                                placeholder="Enter fill value"







                                className="mt-3 w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-white outline-none placeholder:text-white/20 focus:border-purple-400/40"







                              />







                            )}







                          </div>







                        );







                      })}







                      {profile.columns.filter((column) => column.missing > 0).length === 0 && (







                        <p className="text-sm text-emerald-300">No column-level missing-value issues found.</p>







                      )}







                    </div>







                  </div>















                  <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">



                    <p className="text-xs text-white/30">



                      Preview first. Nothing is stored until you apply the cleaning.



                    </p>



                    <button



                      onClick={previewCleaning}



                      disabled={cleaning || cleaningApplied}



                      className="rounded-xl bg-gradient-to-r from-purple-600 to-violet-600 px-6 py-3 text-sm font-semibold transition hover:from-purple-500 hover:to-violet-500 disabled:cursor-not-allowed disabled:opacity-50"



                    >



                      {cleaning ? "Preparing Preview..." : "Preview Cleaning"}



                    </button>



                  </div>















                  {cleaningPreview && (







                    <div className="mt-6 rounded-2xl border border-purple-400/15 bg-purple-500/[0.04] p-5">







                      <h3 className="font-semibold">Cleaning Preview</h3>







                      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">







                        <QualityCard label="Rows Before" value={cleaningPreview.before.row_count.toLocaleString("en-IN")} />







                        <QualityCard label="Rows After" value={cleaningPreview.after.row_count.toLocaleString("en-IN")} />







                        <QualityCard label="Rows Removed" value={cleaningPreview.changes.rows_removed.toLocaleString("en-IN")} />







                        <QualityCard label="Duplicates Removed" value={cleaningPreview.changes.duplicate_rows_removed.toLocaleString("en-IN")} />







                      </div>







                      <div className="mt-4 grid gap-3 sm:grid-cols-2">







                        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">







                          <p className="text-xs uppercase tracking-wider text-white/25">Missing values</p>







                          <p className="mt-2 text-sm text-white/60">







                            {cleaningPreview.before.missing_value_count} → {cleaningPreview.after.missing_value_count}







                          </p>







                        </div>







                        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">







                          <p className="text-xs uppercase tracking-wider text-white/25">Filled values</p>







                          <p className="mt-2 text-sm text-white/60">







                            {Object.entries(cleaningPreview.changes.filled_values).map(([column, info]) => `${column}: ${info.count}`).join(" · ") || "None"}







                          </p>







                        </div>







                      </div>







                      <p className="mt-4 text-xs text-white/30">



                        This is a preview only. The dataset has not been stored yet.



                      </p>







                      {!cleaningApplied ? (



                        <div className="mt-5 flex flex-col gap-3 rounded-2xl border border-emerald-400/15 bg-emerald-500/[0.04] p-4 sm:flex-row sm:items-center sm:justify-between">



                          <div>



                            <p className="text-sm font-medium text-emerald-200">



                              Ready to apply



                            </p>



                            <p className="mt-1 text-xs text-white/30">



                              This will clean the dataset using the decisions shown above and store the cleaned version.



                            </p>



                          </div>







                          <button



                            onClick={applyCleaning}



                            disabled={cleaning}



                            className="rounded-xl bg-emerald-500 px-6 py-3 text-sm font-semibold text-black transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"



                          >



                            {cleaning ? "Applying..." : "Apply Cleaning"}



                          </button>



                        </div>



                      ) : (



                        <div className="mt-5 rounded-2xl border border-emerald-400/20 bg-emerald-500/[0.08] p-4">




                          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">




                            <div>




                              <p className="text-sm font-semibold text-emerald-300">




                                ✓ Cleaning applied successfully




                              </p>




                              <p className="mt-1 text-xs text-white/40">




                                Your cleaned dataset has been stored and is ready for analysis.




                              </p>




                            </div>




                            <button




                              type="button"




                              onClick={downloadCleanedDataset}




                              disabled={downloadingCleaned}




                              className="shrink-0 rounded-xl bg-white px-5 py-3 text-sm font-semibold text-black transition hover:bg-white/90 disabled:cursor-not-allowed disabled:opacity-50"




                            >




                              {downloadingCleaned ? "Preparing CSV..." : "↓ Download Cleaned Data"}




                            </button>




                          </div>




                        </div>



                      )}



                    </div>







                  )}







                </>







              )}







            </div>







          )}































          {error && fileName && (















            <div className="mt-5 rounded-xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">















              {error}















            </div>















          )}































        </section>































        {/* =================================================

            DATASET INTELLIGENCE

        ================================================= */}



        {fileName && (intelligenceLoading || intelligence || intelligenceError) && (

          <section className="mt-6 rounded-3xl border border-purple-400/10 bg-gradient-to-b from-purple-500/[0.05] to-white/[0.02] p-6">

            <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">

              <div>

                <p className="text-xs uppercase tracking-[0.2em] text-purple-300/60">

                  Dataset Intelligence

                </p>

                <h2 className="mt-2 text-xl font-semibold">Understanding your data</h2>

                <p className="mt-1 text-xs text-white/30">

                  Universal structural analysis — independent of industry or dataset type.

                </p>

              </div>



              {intelligenceLoading && (

                <span className="rounded-full border border-purple-400/20 bg-purple-500/10 px-3 py-1.5 text-xs text-purple-200">

                  Analyzing dataset...

                </span>

              )}



              {intelligence && !intelligenceLoading && (

                <span className="rounded-full border border-emerald-400/20 bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-300">

                  Intelligence ready

                </span>

              )}

            </div>



            {intelligenceError && (

              <div className="mt-4 rounded-xl border border-yellow-400/20 bg-yellow-500/10 px-4 py-3 text-sm text-yellow-200">

                Intelligence could not be generated: {intelligenceError}

              </div>

            )}



            {intelligence && (

              <>

                <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">

                  <QualityCard

                    label="Detected Domain"

                    value={

                      intelligence.dataset_domain?.domain

                        ? intelligence.dataset_domain.domain.replaceAll("_", " ")

                        : "General analytics"

                    }

                  />

                  <QualityCard

                    label="Domain Confidence"

                    value={

                      typeof intelligence.dataset_domain?.confidence === "number"

                        ? `${(intelligence.dataset_domain.confidence * 100).toFixed(0)}%`

                        : "—"

                    }

                  />

                  <QualityCard

                    label="Rows Analyzed"

                    value={

                      typeof intelligence.row_count === "number"

                        ? intelligence.row_count.toLocaleString("en-IN")

                        : profile?.row_count.toLocaleString("en-IN") ?? "—"

                    }

                  />

                  <QualityCard

                    label="Columns Analyzed"

                    value={

                      typeof intelligence.column_count === "number"

                        ? intelligence.column_count.toLocaleString("en-IN")

                        : profile?.column_count.toLocaleString("en-IN") ?? "—"

                    }

                  />

                </div>



                <div className="mt-5 grid gap-4 lg:grid-cols-3">

                  <div className="rounded-2xl border border-white/[0.07] bg-black/20 p-5">

                    <p className="text-xs uppercase tracking-wider text-white/25">Column Roles</p>

                    <div className="mt-3 space-y-2">

                      {Object.entries(intelligence.role_counts ?? {}).map(([role, count]) => (

                        <div key={role} className="flex items-center justify-between text-sm">

                          <span className="capitalize text-white/60">

                            {role.replaceAll("_", " ")}

                          </span>

                          <span className="font-medium text-white/85">{count}</span>

                        </div>

                      ))}

                    </div>

                  </div>



                  <div className="rounded-2xl border border-white/[0.07] bg-black/20 p-5">

                    <p className="text-xs uppercase tracking-wider text-white/25">Metric Candidates</p>

                    <div className="mt-3 flex flex-wrap gap-2">

                      {(intelligence.metric_candidates ?? []).length > 0 ? (

                        intelligence.metric_candidates?.map((metric, index) => (

                          <span

                            key={`${metric.column ?? metric.name ?? "metric"}-${index}`}

                            className="rounded-lg border border-purple-400/15 bg-purple-500/10 px-3 py-2 text-xs text-purple-200"

                          >

                            {metric.column ?? metric.name ?? "Unnamed metric"}

                          </span>

                        ))

                      ) : (

                        <span className="text-sm text-white/30">No metric candidates detected yet.</span>

                      )}

                    </div>

                  </div>



                  <div className="rounded-2xl border border-white/[0.07] bg-black/20 p-5">

                    <p className="text-xs uppercase tracking-wider text-white/25">Analysis Opportunities</p>

                    <div className="mt-3 space-y-2">

                      {(intelligence.analysis_opportunities ?? []).length > 0 ? (

                        intelligence.analysis_opportunities?.slice(0, 6).map((opportunity, index) => (

                          <div

                            key={`${opportunity.type ?? opportunity.name ?? "analysis"}-${index}`}

                            className="rounded-lg bg-white/[0.03] px-3 py-2 text-xs capitalize text-white/60"

                          >

                            {(opportunity.name ?? opportunity.type ?? "Analysis").replaceAll("_", " ")}

                          </div>

                        ))

                      ) : (

                        <span className="text-sm text-white/30">

                          No analysis opportunities detected yet.

                        </span>

                      )}

                    </div>

                  </div>

                </div>

              </>

            )}

          </section>

        )}



        {/* =================================================
            DYNAMIC KPI CARDS
        ================================================= */}

        <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {kpis.length > 0 ? (
            kpis.map((kpi) => (
              <KpiCard
                key={kpi.key}
                label={kpi.label}
                value={formatDynamicKpiValue(kpi)}
              />
            ))
          ) : (
            <div className="col-span-full rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-6 text-center">
              <p className="text-sm text-white/30">Dynamic KPIs will appear after your dataset is inspected.</p>
            </div>
          )}
        </section>

        {cleaningApplied && kpis.length > 0 && (
          <p className="mt-3 text-xs text-white/25">KPIs updated from the cleaned dataset.</p>
        )}

        {/* =================================================















            AI ANALYST















        ================================================= */}































        <section className="mt-6 rounded-3xl border border-purple-400/10 bg-gradient-to-b from-purple-500/[0.05] to-white/[0.02] p-6">































          {/* AI Header */}































          <div className="flex items-center gap-3">































            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10 text-lg text-purple-300">















              ✦















            </div>































            <div>















              <h2 className="font-semibold">















                AI Analyst















              </h2>































              <p className="text-xs text-white/30">
                Ask questions about your data in plain English
              </p>

              {billingUser?.is_admin ? (
                <span className="mt-2 inline-flex rounded-full border border-amber-400/15 bg-amber-500/10 px-2.5 py-1 text-[10px] font-medium text-amber-300">
                  DEVELOPER · Unlimited AI
                </span>
              ) : billingUser?.plan === "pro" ? (
                <span className="mt-2 inline-flex rounded-full border border-emerald-400/15 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-medium text-emerald-300">
                  PRO · Unlimited AI
                </span>
              ) : (
                <span className="mt-2 inline-flex rounded-full border border-purple-400/15 bg-purple-500/10 px-2.5 py-1 text-[10px] font-medium text-purple-200">
                  FREE · {Math.max(0, 1 - (billingUser?.ai_questions_used ?? 0))} question remaining
                </span>
              )}















            {!billingUser?.is_admin && billingUser?.plan !== "pro" && (
              <button
                type="button"
                onClick={upgradeToPro}
                disabled={billingLoading}
                className="ml-auto rounded-xl bg-gradient-to-r from-purple-600 to-violet-600 px-4 py-2.5 text-xs font-semibold shadow-lg shadow-purple-900/20 transition hover:from-purple-500 hover:to-violet-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {billingLoading ? "Opening..." : "Upgrade to Pro · ₹499/month"}
              </button>
            )}
            </div>































          </div>































          {kpis.length === 0 ? (































            <div className="mt-5 flex min-h-[150px] items-center justify-center rounded-2xl border border-dashed border-white/10 bg-black/20">































              <div className="text-center">































                <p className="text-sm text-white/30">















                  Upload a dataset to activate AI Analyst















                </p>































                <p className="mt-2 text-xs text-white/20">















                  Ask questions about sales, profit, products,















                  customers and more.















                </p>































              </div>































            </div>































          ) : (































            <>































              {/* Suggested questions */}































              <div className="mt-5 flex flex-wrap gap-2">































                {suggestedQuestions.map((item) => (































                  <button















                    key={item}















                    onClick={() => askAI(item)}















                    disabled={asking}















                    className="rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-xs text-white/50 transition hover:border-purple-400/30 hover:bg-purple-500/10 hover:text-purple-200 disabled:cursor-not-allowed disabled:opacity-50"















                  >















                    {item}















                  </button>































                ))}































              </div>































              {/* Question input */}































              <form















                onSubmit={handleQuestionSubmit}















                className="mt-5"















              >































                <div className="flex flex-col gap-3 sm:flex-row">































                  <input















                    value={question}















                    onChange={(event) =>















                      setQuestion(event.target.value)















                    }















                    placeholder="Ask anything about your dataset..."















                    disabled={
                      asking ||
                      (!billingUser?.is_admin &&
                        billingUser?.plan !== "pro" &&
                        (billingUser?.ai_questions_used ?? 0) >= 1)
                    }















                    className="flex-1 rounded-xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none placeholder:text-white/20 focus:border-purple-400/40"















                  />































                  <button















                    type="submit"















                    disabled={
                      asking ||
                      !question.trim() ||
                      (!billingUser?.is_admin &&
                        billingUser?.plan !== "pro" &&
                        (billingUser?.ai_questions_used ?? 0) >= 1)
                    }















                    className="rounded-xl bg-gradient-to-r from-purple-600 to-violet-600 px-6 py-3 text-sm font-semibold transition hover:from-purple-500 hover:to-violet-500 disabled:cursor-not-allowed disabled:opacity-40"















                  >















                    {asking ? "Thinking..." : "Ask AI"}















                  </button>































                </div>































              </form>































              {!billingUser?.is_admin &&
                billingUser?.plan !== "pro" &&
                (billingUser?.ai_questions_used ?? 0) >= 1 &&
                !asking && (
                  <div className="mt-5 flex flex-col gap-3 rounded-2xl border border-purple-400/15 bg-purple-500/[0.05] p-5 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="text-sm font-medium text-purple-200">
                        Free AI question used
                      </p>
                      <p className="mt-1 text-xs text-white/35">
                        Upgrade to Pro for unlimited AI Analyst questions.
                      </p>
                    </div>

                    <button
                      onClick={upgradeToPro}
                      disabled={billingLoading}
                      className="rounded-xl bg-purple-600 px-5 py-2.5 text-xs font-semibold transition hover:bg-purple-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {billingLoading
                        ? "Processing..."
                        : "Upgrade to Pro · ₹499/month"}
                    </button>
                  </div>
                )}

              {/* Loading */}































              {asking && (















                <div className="mt-5 rounded-2xl border border-purple-400/10 bg-purple-500/[0.04] p-5">































                  <div className="flex items-center gap-3">































                    <div className="h-2 w-2 animate-pulse rounded-full bg-purple-400" />































                    <p className="text-sm text-purple-200">















                      Analyzing your data...















                    </p>































                  </div>































                  <p className="mt-2 text-xs text-white/25">















                    Groq is generating and validating the analysis.















                  </p>































                </div>















              )}































              {/* Error */}































              {aiError && (















                <div className="mt-5 rounded-xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">















                  {aiError}















                </div>















              )}































              {/* Latest answer */}































              {answer && !asking && (















                <div className="mt-5 rounded-2xl border border-purple-400/20 bg-purple-500/[0.06] p-6">































                  <div className="flex items-center gap-2">































                    <span className="text-purple-300">















                      ✦















                    </span>































                    <span className="text-xs font-medium uppercase tracking-wider text-purple-300/70">















                      AI Insight















                    </span>































                  </div>































                  <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-white/80">















                    {answer}















                  </p>































                </div>















              )}































              {/* Conversation history */}































              {chatHistory.length > 1 && (















                <div className="mt-6">































                  <p className="mb-3 text-xs uppercase tracking-wider text-white/20">















                    Recent Questions















                  </p>































                  <div className="space-y-3">































                    {chatHistory















                      .slice(0, -1)















                      .slice(-3)















                      .reverse()















                      .map((chat, index) => (































                        <div















                          key={`${chat.question}-${index}`}















                          className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4"















                        >































                          <p className="text-xs text-purple-300/70">















                            {chat.question}















                          </p>































                          <p className="mt-2 text-sm leading-6 text-white/50">















                            {chat.answer}















                          </p>































                        </div>































                      ))}































                  </div>































                </div>















              )}































            </>































          )}































        </section>































      </div>































    </main>















  );















}































// ============================================================















// HELPERS















// ============================================================































function formatDynamicKpiValue(kpi: DynamicKpi): string {
  const value = kpi.value;
  if (value === null || value === undefined) return "—";

  if (kpi.format === "date" && typeof value === "object") {
    const start = value.start ? new Date(value.start).toLocaleDateString("en-IN") : "";
    const end = value.end ? new Date(value.end).toLocaleDateString("en-IN") : "";
    return start && end ? `${start} – ${end}` : start || end || "—";
  }

  if (typeof value === "number") {
    if (kpi.format === "percent") return `${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}%`;
    if (kpi.format === "currency") return value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
    if (kpi.format === "number") return value.toLocaleString("en-IN", { maximumFractionDigits: 0 });
    return value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
  }

  return String(value);
}


function formatCrore(value: number) {















  return `₹${(value / 10000000).toFixed(2)} Cr`;















}































function QualityCard({ label, value }: { label: string; value: string }) {







  return (







    <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-4">







      <p className="text-xs uppercase tracking-wider text-white/25">{label}</p>







      <p className="mt-2 text-xl font-semibold">{value}</p>







    </div>







  );







}















function ChoiceButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {







  return (







    <button type="button" onClick={onClick} className={`rounded-lg border px-3 py-2 text-xs font-medium transition ${active ? "border-purple-400/40 bg-purple-500/15 text-purple-200" : "border-white/10 bg-white/[0.03] text-white/50 hover:border-white/20 hover:text-white"}`}>







      {children}







    </button>







  );







}















// ============================================================















// KPI CARD















// ============================================================































function KpiCard({















  label,















  value,















}: {















  label: string;















  value: string;















}) {















  return (















    <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-5">































      <p className="text-xs uppercase tracking-wider text-white/25">















        {label}















      </p>































      <p className="mt-3 text-2xl font-semibold">















        {value}















      </p>































      <p className="mt-2 text-[11px] text-white/20">















        {value === "—"















          ? "Waiting for dataset"















          : "From uploaded dataset"}















      </p>































    </div>















  );















}