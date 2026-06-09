# A deep-learning advance for species distribution modelling

<div id="authors"></div>

<!-- Converted from temp/dSDM_MS_draft.docx on 2026-05-27 with Pandoc 3.9.0.2. Early draft; citation and reference cleanup pending. -->

## Abstract

To do…


## Introduction

Species distribution modelling (SDM) is a widely used in ecology and conservation biology to predict habitat suitability and forecast range changes in response to environmental variables. Its applications are vital for practical tasks such as habitat-suitability modelling and anticipating climate-change impacts and range shifts. The modelling process can leverage a rich array of climate, vegetation, land-use, and other spatial data, to predict presence-absence or presence-only occurrence data. Historically, SDM evolved from analytical statistical models through to the current predominance of machine learning. This progressive shift towards the use of more sophisticated, data-driven techniques in SDM was driven by both improvements in algorithms and the increasing availability of data and resources, including high-performance computing infrastructure, a broad coverage and high resolution of remotely sensed spatial layers, and increasingly comprehensive species-occurrence databases like the Global Biodiversity Information Facility (GBIF) and its national counterparts.

The most used methods for modelling binary presence-absence observational data in SDM include traditional parametric approaches like Generalized Linear Models (GLM), Generalized Additive Models (GAM). Increasingly however, nonparametric algorithms have predominated, including piecewise Multi-variate Adaptive Regression Splines (MARS) for linear and nonlinear relationships, Support Vector Machines (SVM) for high-dimensional spaces, Artificial Neural Networks (ANN) for complex pattern recognition, and decision- tree-based algorithms like Random Forests (RF) and Gradient Boosting Machines (GBM) for fitting interpretable, explicitly hierarchical models. For presence-only data, methods like Maximum Entropy (MaxEnt) are favoured, which contrast observed presence locations with a sample of background environmental conditions. The current state-of-the-art in SDM-based forecasting often involves an ensemble of models, which integrate the predictions from multiple techniques, thereby offering potentially more robust solutions that capture the complexity of species' geographic distributions under various constraints.

Despite the burgeoning use of machine-learning approaches in SDM, the application of ANNs for presence-absence data is limited compared to SVM, RF, and GBM. This disparity in interest has been shaped by both the perception and practicality of ANNs. First, the complexity of ANNs, particularly in terms of hyperparameter tuning, has posed challenges. While all machine learning methods require careful tuning to balance model complexity and generalisation ability, ANNs often present a larger and more intricate search space. Factors such as the number of hidden layers, neurons per layer, activation functions, learning rates, and regularisation approaches, must all be considered, presenting a daunting prospect even for ecologists well-versed in machine learning. Second, the substantial data demands of ANNs, in contrast to RF and GBM's robustness to overfitting and suitability for smaller datasets, can be a significant barrier in ecological studies where data on rare or poorly monitored species are often scarce. Further, the historical use of ANNs in SDM has been synonymous with shallow neural networks, consisting of a single hidden layer. Libraries like *nnet*, designed for shallow networks, are easy to use but offer limited flexibility for implementing more complex architectures and training schedules. Lastly, the interpretability of ANNs is often expressed as a concern. In a field where understanding underlying ecological relationships is often as vital as predictive accuracy, the "black box" nature of ANNs can act as a deterrent, more so than other statistical- and machine-learning algorithms. In short, reasons for the limited adoption of ANNs in SDM is multifaceted, rooted in practical challenges, historical trends, and the specific needs and goals of ecological research. However, the field of deep learning has recently made great strides, with increasingly sophisticated tools and methodologies become more accessible. In this context, the field is ripe for change. The exploration of more complex neural-network architectures (‘deep learning’), moving beyond the constraints of shallow networks, coupled with rigorous validation and tuning, offers the prospect of new innovations in species distribution modelling.

The evolution of deep learning over the past two decades has been marked by a series of advancements that have transformed the field. In the 1990s and early 2000s, the capabilities of neural networks were confined by multiple constraints, including as a lack of robust algorithms for training deep networks, along with limited available computational power and data availability. This deterred the training of more complex models. Theoretical and algorithmic developments were in their infancy, with many of the now-standard optimisation algorithms, activation functions, and regularisation techniques yet to be devised. Software and tooling were rudimentary, with ANN libraries available for SDM in R offering basic functionality but lacking the sophistication of modern frameworks like *Keras* and *Tensorflow*. Further, the community and collaboration around deep learning were limited, especially for ecologists, and educational resources were scarce.

Today, by contrast, the deep-neural-network landscape has been revolutionised by a slew of technical advances, including: i) more robust starting weights, such He or Xavier initialisations, and activation functions like ReLU (rectified linear unit), which mitigate vanishing or exploding gradients; ii) advanced optimisation algorithms like Adam and RMSprop, which along with batch normalisation, to improve convergence and stability during learning; iii) regularisation methods like dropout and weight decay, which guard against overfitting when training complex model architectures; iv) use of Graphics Processing Units (GPU) to reduce training times and permit larger models; v) automated hyperparameter tuning to simplify model optimisation; vi) pre-trained models that enable transfer learning; vii) big-data integration and data augmentation that allows scalable training; viii) end-to-end learning that facilitates more direct input of data, as feature engineering can be learned as part of the training process; and ix) a now-thriving research community that lower barriers to entry. These advancements have expanded the available capabilities whilst simultaneously making deep learning more accessible to non-specialist domains, including ecology. In terms of implementation of these innovations, a user-friendly application programming interfaces, exemplified by *Keras*, providing seamless integration with data analysis environments like R and Python, now allows for a more cohesive workflow that combines traditional data analysis with deep learning.

Notably, the adoption of techniques such as transfer learning and data augmentation has been conspicuously absent from SDM. Transfer learning is a method that leverages pre-trained models to enhance performance on related tasks and is now commonplace in applications like image classification and natural-language processing. Conceptually, transfer learning shares with Bayesian priors the idea of leveraging previous knowledge, though it differs in its theoretical underpinning and lacks any strict probabilistic interpretation. However, the often-high degree of specificity of non-visual ecological data and the traditional reliance on machine-learning methods have meant that this approach has not been part of the SDM toolkit to date. Indeed, methods like decision trees and SVMs are typically trained from scratch for each specific task because they lack the shared feature representations that make transfer learning applicable, limiting their adaptability to pre-trained models. It is a similar story for data augmentation, a strategy to artificially increase the size and diversity of a training dataset. Unlike in domains such as computer vision, where simple transformations can create meaningful augmentations, the complexity and specificity of SDM data present unique challenges. For instance, generic augmentation techniques risk introducing bias or distorting underlying geographic, climatic, and ecological relationships. Furthermore, the traditional focus on machine-learning methods that do not typically benefit from data augmentation has left this potentially powerful technique underexplored. These gaps in the application of transfer learning and data augmentation reflect a broader disconnect between the rapid advancements in deep learning and their limited integration into SDM. In short, while deep learning has revolutionised various fields by enabling the modelling of complex, hierarchical relationships, its potential in SDM remains untapped. Yet, as the demand for reliable, scalable, and generalisable SDM predictions continues to grow, the exploration of innovative techniques is a pressing necessity.

Despite the remarkable success of deep learning in data science over the last decade, the state-of-the-art for SDM remains firmly anchored in traditional machine-learning methods like regression splines, discriminant analysis, vector machines, and decision trees. This reflects a complex historical interplay of technological, theoretical, software, community, educational factors, and intellectual inertia. While there are a few recent exceptions, such as the use of convolutional neural networks in X and Y, these applications remain far from mainstream, often seen as novel case-specific applications rather than integral components of the SDM workflow. Here, we seek to demonstrate how deep learning can reduce the need for feature engineering and allow for innovative techniques such as data augmentation and transfer learning, which can improve generalisation and model predictions. This is especially vital for taxa where training data are constrained due to few observations or inherent species rarity, a common challenge in ecological and conservation studies.

Our aims are threefold: 1) to show how data augmentation and transfer learning can be implemented in SDM, providing practical insights and methodologies that align with ecological principles; 2) to compare the performance on spatially sampled test data, for two case studies, of a deep-learning approach to SDM versus traditional machine-learning methods (e.g., GAM, RF, GBM, model ensembles), offering an empirical assessment of the potential gains in accuracy and efficiency; and 3) to evaluate whether transfer learning is best done via paired species (using the most ecologically similar species as a template), a sequential approach (gradually refining transfer weights from species-to-species), or a ‘melting-pot’ (wherein all species data except the target are aggregated in a pool of site-by-site training data). By exploring these avenues, we hope to bridge the gap between the rapid software-engineering advancements in deep learning and its promise for innovation in, and improved accuracy and scalability of, species distribution modelling.


## Methods

*Development environment, major packages used, and code repository*

The code-development environment for this study, the R language (currently v4.3.1), was chosen to align with the tools and scripting languages most commonly used by ecologists for species distribution modelling. A suite of modern specialised R libraries was used to facilitate various aspects of the modelling process. The package *galah* was employed for online species-occurrence-data extraction, providing a streamlined interface for accessing relevant observational data from the Atlas of Living Australia. For handling spatial vector and raster data, the *sf* and *terra* packages respectively, were used. The *tidyverse* packages were integrated for efficient data handling, while *spatialsample* was used for spatial-data partitioning when generating training folds and test data. For the machine-learning component, the *tidymodels* and *tidysdm* frameworks were chosen, as they use tidyverse principles and provide a streamlined and consistent workflow. Finally, for the deep-learning modelling, the *keras* and *tensorflow* packages were leveraged. In aggregate, these package choices reflect a balance between cutting-edge capabilities and alignment with standard ecological modelling practices. The code repository, replication workflow, and datasets, are openly available at <https://github.com/bwbrook/dsdm>, thereby ensuring transparency.

*Case studies*

Two case studies are presented, providing useful comparisons for different taxa and spatial scales.

The first involves nine mammal species from the large temperate island of Tasmania and its archipelago, located off southern mainland Australia. These species have monitored with a wide-ranging long-term camera trapping study and are also regularly reported by citizen scientists. Tasmania’s habitats include wet and dry eucalyptus forest, non-eucalypt rainforest, and native and introduced grasslands. The selected species, all being conspicuous native marsupials that are readily identifiable, are three medium-to-large-sized herbivorous grazing/browsing macropods: Tasmanian pademelon *Thylogale billardierii*, Bennetts wallaby *Notamacropus rufogriseus* and Forester kangaroo *Macropus giganteus*; two herbivorous browsing possums: Brushtail *Trichosurus vulpecula* and Ringtail *Pseudocheirus peregrinus*; the grazing semi-fossorial bare-nosed wombat *Vombatus ursinus*; and three carnivorous Dasyurid predators/scavengers: Tasmanian devil *Sarcophilus harrisii*, Spotted-tail quoll *Dasyurus maculatus* and Eastern quoll *Dasyurus viverrinus*.

The second models 100 terrestrial bird species from across south-eastern Australia (listed in the Supplementary Material), encompasses areas of broad-leaf and mixed forests and woodland sites with a temperate climate (Fig. S1). Using the Interim Biogeographic Regionalisation for Australia (IBRA), the regions of interest were identified based on the prevalence of wet and dry eucalypt forests, rainforests, and both native and introduced grasslands. Arid inland zones and tropical broad-leaf forests were excluded due to their unique ecological communities. Among these bird species are emblematic, wide-ranging ones like the Laughing Kookaburra (*Dacelo novaeguineae*) through to those facing threats, such as the range-restricted Forty-spotted Pardalote (*Pardalotus quadragintus*). All selected species are diurnal, can be readily identified both visually and audibly, vary in size, and belong to a range of trophic levels encompassing diverse diets.

*Data sources*

Occurrence data were derived from two sources. For both case studies, the Atlas of Living Australia (ALA, ala.org.au) was drawn on for species observations. The ALA serves as a unified, digital platform that consolidates various Australian biodiversity data and is linked to GBIF, accessed in R via the *galah* interface. Bird occurrences within the study extent recorded from 1970 onward were downloaded from ALA. For these data, only records supplied by eBird, Birdlife Australia, iNaturalist, Atlas of NSW Wildlife, Victorian Biodiversity Atlas, NSW Bird Atlassers, and Tasmanian Natural Values Atlas were used; these sources have robust data-collection and moderation/error-correction protocols. For the Tasmanian mammal case study, site-occupancy data from a long-term (5-year) camera trapping study, which measured both presence and true-absence of species and covered \>1,300 monitoring sites, was merged with the ALA datasets.

Spatial data layers covering south-eastern Australian (including Tasmania) were stacked in a GeoTIF at a resolution of 0.01 decimal degrees in the ESPG 4326 (WGS84) coordinate reference system. This stack consisted of the 19 bioclimatic layers from WorldClim (covering a range of temperature, precipitation, and seasonality variables), as well as six continuous non-climatic variables: elevation, topographic roughness, distance to fresh water, distant to road, FPAR, human footprint, and three categorical variables: land use (17 classes), soil type (12 classes), vegetation type (21 classes). A full meta-data description, including all data sources, is tabulated in the Supplementary Information.

*Data pre-processing and spatial sampling*

The positional data of the ALA occurrences were first snapped to the GeoTIF stack, with each 0.01-degree grid cell allocated a presence (1) if a given species had been observed there. Pseudoabsences (0) were then generated for each species, based on grid cells that had records for at least three species (ensuring adequate local surveying effort), but not the target species. For the Tasmanian case study, those grid cells where long-term camera-trapping data was available had information on true absences. As such, ALA occurrence data (and associated pseudoabsence generation) for Tasmanian mammals was only used for those grid cells that had not been camera trapped. For each species, the gridded occurrence data was then spatially thinned, to ameliorate the biases associated with uneven sampling intensity of populated areas compared to remote regions (method described in Amin et al. 2022), and to set a minimum distance (5 km) between presences and pseudoabsences.

For each case study, the occurrence data were split into training and test sets and anchored to the spatial layers. The splits were done using the spatial-clustering method of the *spatialsample* package, by first generating 50 folds. Five spatially disjunct folds were then reserved for the independent test set, and the remaining 45 were randomly allocated to five aggregated folds, for use in cross-validation. The spatially layered map data (input features for the machine learning) were transformed prior to modelling: continuous variables were rescaled to have a mean of 0 and standard deviation of 1, and categorical variables were one-hot encoded. The continuous-variable scaling was based on the training data only, to avoid any leakage of information from the test data.

The original and processed data files, along with the R code provided on the GitHub site, together allow for full replication of the post-processing and spatial sampling of these data, including specifications of the parameter settings used in the sampling algorithms.

*Machine-learning methods*

For the traditional machine-learning (ML) approach, ANN and RF models were fitted individually using *tidysdm*. In addition, an unweighted ensemble of GLM, GAM, ANN, RF and GBM was also used. The model-development process began with the most complex feature space, fitting all combinations of predictors to each model. Models were then evaluated using five-fold cross-validation (see above), wherein the feature space was gradually simplified by removing predictors and assessing the impact on performance. If the exclusion of a feature led to a substantial drop in mean out-of-sample performance (AUC by 1 point or more), that feature was retained. When two predictors exhibited the same effect, the one grounded in ecological explanation was retained. This iterative process continued while the simplified model still produced the best model fit on the cross-validation data. For the ensemble model, the feature selection was identical for each component algorithm.

*Deep-learning model*

The deep-learning SDM (hereafter ‘dSDM’) was built using the *Keras* sequential and functional APIs. The architecture is a fully connected, multi-layer feed-forward neural network model, trained with binary cross-entropy loss and the adam optimiser. The model width (number of hidden neurons per layer) and depth (number of densely connected layers) were determined by hyper-parameter tuning (see next section). A hidden compression layer with a reduced number of neurons, set at one-quarter the width of the other hidden layers, was incorporated before the output layer to encourage a more compact and focused feature representation. Batch normalisation was used between each dense layer to stabilise learning and improve convergence speed. Two forms of explicit regularisation were used to promote generalisation: stochastic dropout and elastic-net weight decay. The ReLU activation function was used for all intermediate layers, and sigmoid for the final prediction.

*Hyper-parameter tuning*

During feature selection, the ML model hyper-parameters were left at default values. Once the model architecture had been decided, a grid search was used to select the optimal hyper-parameter values, based on minimising cross-validated (out-of-sample) loss. There was no tuning done for GLM or GAM. For ANN, decay was tuned across 1e<sup>-2</sup>, 1e<sup>-3</sup> or 1e<sup>-4</sup>, and hidden units: 64, 128 or 256. For RF, the ntrees was fixed at 1000 and mtry was tuned over the integers 1:7. For GBM, shrinkage was tuned across 1e<sup>-2</sup>, 1e<sup>-3</sup> or 1e<sup>-4</sup>, interaction depth: 1, 5 or 9, and n.minobsinnode: 10, 20 or 30. Starting with 100, ntrees in GBM was incremented by 100 to a maximum of 1500. For the dSDM, the following hyper-parameters were grid-search tuned: (i) *architecture*: depth: 3, 4 or 5; width: 64, 128 or 256; (ii) *regularisation*: L1/L2 lambda (separately): 1e<sup>-2</sup>, 1e<sup>-3</sup> or 1e<sup>-4</sup>; and dropout: 0.2, 0.35 or 0.5.

*Transfer Learning approaches*

Four transfer-learning (pre-training) experiments were run for the dSDM:

1)  *No transfer*: dSDM model weights initialised randomly and trained exclusively on target species’ data. This is how all the other ML models (ANN, RF, GBM, ensemble) were trained.

2)  *Paired*: dSDM first trained on an ecologically similar taxon to the target species, and then fine-tuned on data from the target data.

3)  *Sequential*: dSDM trained on a baseline widespread species, and then serially refined on each other species, with the final fine-tuning being done on the target species’ data.

4)  *Community*: training initially undertaken on the pooled occurrence data (i.e., all species except for the target species); grid cells can be represented by both presences and absences of given species in the community, resulting in a multi-species occupancy model. This dSDM was then fine-tuned on presence-absence data from the target species.

Experiments 2–4 take advantage of the inherent architectural properties of neural networks trained with backpropagation, which permit the retention and transfer of knowledge (patterns encapsulated in learned features and representations) across different datasets, through updating the model state.

*Data augmentation*

We devised a novel data-augmentation strategy for the dSDM, via jittering species-occurrence locations. The principle behind this approach is to account for the inherent uncertainty and natural variability in species occupancy of landscapes, and thus create a richer training dataset for the deep-learning model. In the implementation, each occurrence point was jittered by a predefined distance, following a two-dimensional Gaussian point-spread distribution. This technique uses polar coordinates to simulate a radially symmetrical spread around a location, with the highest probability of an occurrence remaining in its original grid cell, and progressively diminishing probabilities of being jittered to nearby grid cells as the distance from the original location increases. Here the spread was set such that 75% of the data points were within zero to three grid cells of their original location. In general, the spread parameter should be chosen based on ecological considerations, reflecting a reasonable expected movement range for a given species that extends beyond the granularity of the spatial grid. This process will also introduce noise into the data (e.g., the possibility of jittering points into unsuitable habitat); such augmentation has been shown to have a regularising effect that helps mitigate overfitting when deep learning. Each epoch (i.e., one full pass of the data) of final fine-tuning stage of model training for the dSDM used a new jitter-augmented dataset.

*Performance metrics and threshold tuning*

Model performance on the held-out test data was assessed using various metrics: Area Under the Curve (AUC) of the Receiver Operating Characteristic (AUC ROC) and Precision-Recall (AUC-PR), True Skill Statistic (TSS), Sensitivity, Specificity, Balanced Accuracy, Matthew’s Correlation Coefficient (MCC), and the F1 score. Given the class imbalance in the data of some species, threshold tuning was used to map probabilities to presence/absence labels. The F1 score, which emphasises the minority class and balances the Precision-Recall trade-off, was used for this threshold tuning.


## Results

1\. Results of hyper-parameter tuning

2\. Base results for / comparison of, the ML algorithms and the no-transfer dSDM, both case studies.

3\. Tas Mammal: evaluation of:

1)  most effective transfer-learning strategy, and

2)  for best TL strategy:

    1.  naïve performance of the transfer model without fine-tuning, and

    2.  additional effectiveness (if any) of data augmentation on the fine-tuning result.

4\. SE Birds: take forward best TL strategy and evaluate effectiveness relative to base results.


## Discussion

Deep learning is a branch of machine learning that uses artificial neural networks to learn complex patterns from data. This work demonstrates that deep learning models are now a viable method for species distribution modelling, expanding the machine-learning toolkit available to researchers and practitioners. The dSDM performed as well, or better, than any of the more traditional ML approaches, across a wide variety of species and environments embodied in the two case studies. Moreover, dSDM can benefit from both transfer learning and data augmentation, which underscore its value in data-poor situations, because models do not need to be naively (randomly) initialised. … *Update the above to hit main message: key take-aways from the results, across both case studies. Include what worked and what didn’t (if anything). Will need to wait for results to write this properly.*

Notably, the architectural distinctions between the well-known ANN and the new dSDM approach presented here, offer more than just a technical divergence. Traditional ANNs, limited to a single hidden layer, have the useful feature of capturing implicit interactions between variables. dSDM offer additional layered complexity, via multiple hidden layers that are mediated by activation functions like ReLU. This design enables the network to learn hierarchical, non-linear relationships between variables, a capability that is not just incrementally better, but qualitatively different. Rooted in the Universal Approximation Theorem, this potential of dSDM to approximate any continuous function gives them a theoretical edge in capturing the nuanced interplay of ecological factors. Historically, the Achilles' heel of deep neural networks has been the difficulty in training them effectively. Issues like vanishing or exploding gradients often stymied their performance. However, the advent of advanced initialisation and optimisation algorithms, along with regularisation techniques like dropout, weight decay and batch normalisation, has largely neutralised these challenges. Combining these advancements with the knowledge-propagation benefits of transfer learning not only makes deep learning a viable option for species distribution modelling, but arguably a superior one. Further, the relative ease-of-implementation of dSDM in environments familiar to ecologists (e.g., R and Python) is complemented by a now-widespread and low-cost availability of GPU hardware or cloud-compute services for model training. In short, the once-daunting barriers to using deep learning to tackle problems in ecological modelling are rapidly dissolving, opening new avenues for innovation and a deeper understanding of the complexities inherent in natural systems.

The dSDM approach, when underpinned by transfer learning and data augmentation using spatial jittering, shares conceptual similarities with multi-species SDMs, some of which have used convolutional neural networks (CNN). The CNN deep-learning architecture is applied widely in image classification. In a SDM context, CNN can capture explicit spatial relationships of the surrounding environment (e.g., neighbourhood effects) with respect to co-occurrences of multiple species. A recent study demonstrated this approach for a large presence-only dataset of plant species, and showed improved performance compared to other machine learning for the rarer taxa. The notion of transfer learning in dSDM also resonates with the principles underlying joint species distribution models (JSDM). In JSDM, the community structure itself serves as a form of 'prior knowledge,' allowing for more contextual predictions of individual species distributions. The community transfer-learning in dSDM can be seen as a computational analogue to this, where the model is trained on a broad set of species data and then fine-tuned for individual or less-represented species. Indeed, deep learning could be used to implement JSDM directly, by using CNN, recurrent, or autoencoder networks, to model the relationships between species and environment, and to capture the spatial and temporal dynamics of species distributions (e.g., seasonal variations or long-term trends). Bayesian SDMs represent another avenue where informative prior knowledge, spatial autocorrelation and hierarchical structure can be incorporated explicitly into the model. That said, the model specification and computational burden of Bayesian methods, typically requiring extensive Markov Chain Monte Carlo simulations or Integrated Nested Laplace Approximation, can be a deterrent. The dSDM transfer-learning method offers an alternative, straightforward and intuitive pathway for integrating prior information and inter-dependencies, whilst achieving similar ends.

The R codebase we developed for dSDM is architected to be modular and transposable. This design choice aims to facilitate the method’s future evolution into a stand-alone library, or for seamless integration into existing SDM machine-learning workflows. The code could also be readily translated into Python or Julia, two other commonly used data-science platforms. While the current implementation leverages the robust capabilities of packages like *tidymodels* for machine learning and *keras* for deep learning with a *tensorflow* backend, the architecture is sufficiently flexible to accommodate alternative frameworks, such as JAX, which is supported in the upcoming *keras core*.

Taking inspiration from the concept of 'foundation models' in image classification and natural-language processing contexts, we envision the development of large-scale general models, pre-trained on hundreds or thousands of species at regional or global scales. These could then serve as a transfer-learning backbone for species distribution modelling. We draw an analogy here with how ImageNet has catalysed advancements in computer vision, making available a wide variety of large, baseline CNN on which fine-tuning can be undertaken to match specific contexts. In the case of SDM, a repository of pre-trained dSDM could substantially enhance individual research efforts, especially in cases where occurrence data are sparse. These foundational models would encapsulate a broad spectrum of species and environmental variables, offering a generalised base for creating a species-specific dSDM. A researcher could then either only train a new classifier on top of a frozen base, or additionally fine-tune some (or all) of the layers of the base model. Both approaches were demonstrated herein. The utility of such an approach is twofold: it streamlines the modelling process and amplifies predictive performance by capitalising on shared ecological patterns and principles.

What further research directions, in the area of deep learning for SDM, might be on offer? The dSDM framework we have showcased is not a terminus, but a springboard. It could catalyse a multitude of new experiments, from seeking to optimise model structure and hyper-parameters, to discovering new approaches to transfer learning, augmentation, and integration with multi-species data. One such frontier is the exploration of the representation space of the dSDM, particularly with respect to the model's size and architecture. While the current study leverages a multi-layered densely connected feed-forward network, alternative architectures such as residual (skip connections) or transformer (attention) networks can offer unique advantages, especially in capturing spatial and temporal dependencies. Moreover, the dSDM framework allows for the development of sophisticated feature-engineering tools, as an alternative to the fine-tuning of foundation models. In other contexts, deep learning has been used to distil complex, high-dimensional input data into a more manageable, yet information-rich, set of features (akin to principal-component axes). This extracted feature set can then serve as input for other deep or traditional machine-learning approaches. Imagine, for instance, a general habitat-suitability layer that compactly encapsulates the interplay of environmental variables with local richness, akin to the community transfer learning we used herein. The concept of transfer learning, while promising, also warrants further scrutiny. Specifically, what constitutes a 'robust' set of species for pretraining? This needs to be empirically determined, and could involve a systematic evaluation of species diversity, relative abundance, and ecological significance, among other factors. Additionally, the optimisation of hyperparameters in the model could benefit from more advanced techniques like Bayesian optimisation, which can fine-tune the model's performance by navigating the hyperparameter space more efficiently.

In summary, the dSDM framework is more than just a new machine-learning method for fitting SDMs. It also opens the door to a plethora of novel research opportunities, some of which we explored in the two case studies, and others we speculated upon in this discussion. These innovations hold the potential to incrementally (or even radically) advance the field, in ways that are not just theoretically appealing, but also empirically robust and practically actionable.

## Reference Notes

To do (link to Endnote)


## Display Items

**Figure 1.** Example of the architecture and tracking metrics monitored when training a SDM using deep-learning methods. a) Graph of the feed-forward neural network model structure used (here simplified in width and depth) showing inputs, hidden neurons, and the single probabilistic output, densely connected by weights (lines) and biases (not shown). Note that during training the network will be fully connected, due to stochastic dropout of nodes and elastic-net weight decay, both of which introduce regularisation that encourage structural sparsity. b) An example of a multi-epoch training run (one epoch is a full pass of the data) showing the tension of seeking low training loss while avoiding overfitting (shown by worsening validation-data loss, after initial gains).

Show a 2-panel figure, fitted against an interesting example. Can use the plot model to show a neural network?


**Figure 2.** Comparison of the performance of SDM built using a traditional machine-learning method (random forests) and a deep-learning approach with transfer learning and data augmentation. Shown are the Receiver Operator Curves (ROC) and suitability maps (presences are black dots, absences red) for two example species: i) a mammal from Tasmania, Eastern quoll (*Dasyurus viverrinus*) and ii) a bird from southeastern Australia, Laughing kookaburra (*Dacelo novaeguineae*).

Show an 8-panel figure:

Best ML (RF) dSDM

ROC, Map ROC, Map : Tas Mammal

ROC, Map ROC, Map : SE Bird


**Table 1.** Example table of SDM performance metrics on the spatially held-out test data for: i) a mammal from Tasmania, Eastern quoll (*Dasyurus viverrinus*) and ii) a bird from southeastern Australia, Laughing kookaburra (*Dacelo novaeguineae*). For visualisation of these cases, see Fig. 2.

Model Metric1 Metric2 etc.

ANN

RF

Ensemble

dSDM-nt

dSDM-ps

dSDM-sq

dSDM-cm

| **model_type** | **species** | **tp** | **tn** | **fp** | **fn** | **sens** | **spec** | **ba** | **f1** | **auc_roc** | **auc_pr** | **tss** | **mcc** |
|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| ann-only | Dasyurus maculatus | 65 | 33 | 11 | 43 | 0.6 | 0.75 | 0.68 | 0.71 | 0.72 | 0.22 | 0.35 | 0.32 |

*Footnote*: Model types are Artificial Neural Network (ANN), Random Forest (RF), Ensemble: unweighted average of the predictions of a Generalised Linear Model (GLM), Generalised Additive Model (GAM) and Gradient Boosting Machine (GBM), plus ANN and RF, deep-learning Species Distribution Model (dSDM) with no transfer learning (dSDM-nt), dSDM with transfer learning from a paired species (dSDM-ps), dSDM with transfer learning from a cumulative sequence of species (dSDM-sq) and dSDM with transfer learning from an aggregated community of species (dSDM-cm). Key: tp = true positives, tp = true negatives, fp = false positives, fn = false negatives, sens = sensitivity, spec = specificity, ba = balanced accuracy, f1 = F1 score, auc_roc = Area Under the Curve (AUC) of the Receiver Operating Characteristic (AUC ROC), auc_pr = AUC of Precision-Recall (AUC-PR), tss = true skill statistic and mcc = Matthew’s correlation coefficient.


**Table 2.** Frequency table of SDM performance metrics on the spatially held-out test data for nine mammal species from Tasmania. Shown are the number of times a given model/approach was the top-ranked for a species, as judged against each performance metric. For a description of the model types and metrics, see the Footnote to Table 1.

As per Table 1, but don’t show species, tp, tn, fp, or fn.


**Table 3.** Frequency table of SDM performance metrics on the spatially held-out test data for 100 bird species from southeastern Australia. Shown are the number of times a given model/approach was the top-ranked for a species, as judged against each performance metric. For a description of the model types and metrics, see the Footnote to Table 1. Note that for this second, larger case study, only the naïve dSDM approach with no transfer learning (dSDM-nt), and the best-performing transfer-learning approach, the community model (dSDM-cm), were used.

As per Table 2, but no dSDM-ps or dSDM-sq (assuming -cm is best)


## Supplementary Information

<u>full_sdm_results.CSV</u>

Table of performance metrics on the spatially held-out test data for: a) nine mammal species from Tasmania (Case Study 1) and b) 100 bird species from southeastern Australia (Case Study 2).

*Example row of the data frame*:

| **model_type** | **species** | **tp** | **tn** | **fp** | **fn** | **sens** | **spec** | **ba** | **f1** | **auc_roc** | **auc_pr** | **tss** | **mcc** |
|----|----|----|----|----|----|----|----|----|----|----|----|----|----|
| ann-only | Dasyurus maculatus | 65 | 33 | 11 | 43 | 0.6 | 0.75 | 0.68 | 0.71 | 0.72 | 0.22 | 0.35 | 0.32 |

The data frame has dimensions of 14 columns × 545 rows (excluding header)

*Definitions*:

model_type:

1.  Artificial Neural Network (ANN)

2.  Random Forest (RF)

3.  Ensemble: unweighted average of the predictions of a Generalised Linear Model (GLM), Generalised Additive Model (GAM) and Gradient Boosting Machine (GBM), plus ANN and RF

4.  deep-learning Species Distribution Model with no transfer learning (dSDM-nt)

5.  dSDM with transfer learning from multispecies community data (dSDM-cm) (see main paper)

tp = true positives

tp = true negatives

fp = false positives

fn = false negatives

sens = sensitivity

spec = specificity

ba = balanced accuracy

f1 = F1 score

auc_roc = Area Under the Curve (AUC) of the Receiver Operating Characteristic (AUC ROC)

auc_pr = AUC of Precision-Recall (AUC-PR)

tss = true skill statistic

mcc = Matthew’s correlation coefficient

## References
